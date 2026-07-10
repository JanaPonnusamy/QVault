import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.config.knowledge_config import PIPELINE_VERSION, KnowledgeConfig
from app.database.database_manager import ROOT
from app.models.search_source import SearchSource
from app.repositories.knowledge_research_repository import KnowledgeRepository
from app.services import knowledge_prompts as prompts
from app.services.knowledge_executor import BackgroundTaskExecutor
from app.services.knowledge_extraction_service import KnowledgeExtractionService
from app.services.llm_service import LLMService
from app.services.source_search_service import SourceSearchService


class SessionCancelled(Exception):
    """Raised inside the pipeline when the user cancelled the session."""


class KnowledgeResearchService:
    """Orchestrates a research session end-to-end: search (topic mode),
    extraction, per-document LLM analysis, cross-source consensus and report
    generation. All large text lives on disk; SQLite stores paths and
    structured rows only."""

    MAX_ANALYSIS_CHARS = 24000

    def __init__(self, executor=None):
        self.repo = KnowledgeRepository()
        self.executor = executor or BackgroundTaskExecutor()

    # ------------------------------------------------------------ public --

    def start_session(
        self,
        mode,
        input_value,
        source_count,
        source_type,
        ai_provider,
        ai_model,
        temperature=0.2,
        max_tokens=4000,
    ):
        mode = mode.upper()

        if mode not in ("URL", "TOPIC"):
            raise ValueError("mode must be 'URL' or 'TOPIC'")

        if not input_value or not input_value.strip():
            raise ValueError("input_value is required")

        session_id = self.repo.create_session(
            mode=mode,
            input_value=input_value.strip(),
            source_count_requested=1 if mode == "URL" else int(source_count),
            source_type=source_type,
            ai_provider=ai_provider or KnowledgeConfig.llm_provider(),
            ai_model=ai_model or KnowledgeConfig.default_model(),
            storage_directory="",
            pipeline_version=PIPELINE_VERSION,
            temperature=float(temperature),
            max_tokens=int(max_tokens),
        )

        storage_dir = ROOT / KnowledgeConfig.storage_root() / str(session_id)
        storage_dir.mkdir(parents=True, exist_ok=True)

        self.repo.set_session_storage_directory(session_id, str(storage_dir))

        self.executor.submit(self._run_session, session_id)

        return session_id

    def get_session(self, session_id):
        return self.repo.get_session(session_id)

    def cancel_session(self, session_id):
        """Request cancellation. The pipeline stops at its next checkpoint.
        Returns the updated session, or None if it does not exist or is
        already finished."""
        session = self.repo.get_session(session_id)

        if not session:
            return None

        if session["status"] in ("COMPLETED", "FAILED", "CANCELLED"):
            return None

        self.repo.update_session_progress(
            session_id, "CANCELLED", "CANCELLED", session["progress"]
        )

        return self.repo.get_session(session_id)

    def delete_session(self, session_id):
        """Delete a finished session, its rows and its storage directory.
        Returns False if the session does not exist; raises ValueError while
        the session is still running."""
        session = self.repo.get_session(session_id)

        if not session:
            return False

        if session["status"] in ("QUEUED", "RUNNING"):
            raise ValueError("Cancel the session before deleting it.")

        storage_dir = session.get("storage_directory") or ""

        self.repo.delete_session(session_id)

        # Only remove directories the service itself created for this session.
        storage_root = ROOT / KnowledgeConfig.storage_root()
        candidate = Path(storage_dir) if storage_dir else None

        if (
            candidate
            and candidate.is_dir()
            and storage_root in candidate.parents
        ):
            shutil.rmtree(candidate, ignore_errors=True)

        return True

    def list_sessions(self, **filters):
        return self.repo.list_sessions(**filters)

    def get_results(self, session_id):
        session = self.repo.get_session(session_id)

        if not session:
            return None

        documents = self.repo.list_documents_by_session(session_id)

        for document in documents:
            document["analysis"] = self._read_json(document.get("summary_path"))

        consensus = self.repo.get_consensus_by_session(session_id)

        if consensus:
            for key in (
                "common_practices_json",
                "differences_json",
                "conflicting_advice_json",
                "recommendation_json",
            ):
                consensus[key.replace("_json", "")] = json.loads(
                    consensus.pop(key) or "null"
                )

        return {
            "session": session,
            "documents": documents,
            "facts": self.repo.list_facts_by_session(session_id),
            "entities": self.repo.list_entities_by_session(session_id),
            "consensus": consensus,
            "ai_runs": self.repo.list_ai_runs_by_session(session_id),
            "report": self._read_json(session.get("report_path")),
        }

    # ---------------------------------------------------------- pipeline --

    def _run_session(self, session_id):
        try:
            session = self.repo.get_session(session_id)

            mode = session["mode"]
            storage_dir = Path(session["storage_directory"])

            llm = LLMService(provider=session["ai_provider"])
            extraction = KnowledgeExtractionService()

            # -- sources ---------------------------------------------------
            if mode == "TOPIC":
                self._progress(session_id, "SEARCHING", 3)

                sources = SourceSearchService(session["source_type"]).search(
                    session["input_value"],
                    session["source_count_requested"],
                )

                if not sources:
                    raise RuntimeError(
                        f"No sources found for topic '{session['input_value']}'"
                    )
            else:
                sources = [
                    SearchSource(
                        document_type=f"{session['source_type']}_video",
                        source_reference=session["input_value"],
                        title=session["input_value"],
                        url=session["input_value"],
                    )
                ]

            # -- per-document extract + analyze ------------------------------
            total = len(sources)
            analyses = []
            failures = []

            for index, source in enumerate(sources, start=1):
                self._check_cancelled(session_id)

                base = 5 + int(80 * (index - 1) / total)
                span = 80 / total

                document_id = self.repo.create_document(
                    session_id,
                    source.document_type,
                    source.source_reference,
                    source.title,
                    source.url,
                )

                doc_dir = storage_dir / f"document_{index:03d}"

                self.repo.update_document_status(document_id, "PROCESSING")

                try:
                    stage_offsets = {
                        "DOWNLOADING": 0.05,
                        "TRANSCRIBING": 0.35,
                        "OCR": 0.55,
                    }

                    result = extraction.extract(
                        document_type=source.document_type,
                        url=source.url,
                        source_reference=source.source_reference,
                        title=source.title,
                        document_dir=doc_dir,
                        progress=lambda stage, b=base, s=span: self._progress(
                            session_id, stage, int(b + s * stage_offsets.get(stage, 0))
                        ),
                    )

                    self.repo.update_document_extraction(
                        document_id,
                        result.language,
                        result.duration,
                        result.word_count,
                        result.character_count,
                        result.file_size,
                        result.checksum,
                        result.processing_version,
                        result.transcript_path,
                        result.subtitle_path,
                        result.ocr_path,
                        result.merged_text_path,
                    )

                    self._progress(
                        session_id, "ANALYZING", int(base + span * 0.7)
                    )

                    analysis = self._analyze_document(
                        llm, session, document_id, index,
                        result.title, source.document_type,
                        Path(result.merged_text_path), doc_dir,
                    )

                    analyses.append(
                        {
                            "index": index,
                            "document_id": document_id,
                            "title": result.title,
                            "url": source.url,
                            "analysis": analysis,
                        }
                    )

                    self.repo.update_document_status(document_id, "COMPLETED")

                except SessionCancelled:
                    self.repo.update_document_status(
                        document_id, "FAILED", "Cancelled by user"
                    )
                    raise

                except Exception as error:  # noqa: BLE001
                    failures.append(f"{source.title}: {error}")
                    self.repo.update_document_status(
                        document_id, "FAILED", str(error)[:1000]
                    )

            if not analyses:
                raise RuntimeError(
                    "All sources failed. " + " | ".join(failures)[:2000]
                )

            # -- consensus (topic mode with 2+ documents) ---------------------
            consensus = None

            if mode == "TOPIC" and len(analyses) > 1:
                self._progress(session_id, "COMPARING", 88)
                consensus = self._build_consensus(llm, session, analyses)

            # -- report --------------------------------------------------------
            self._progress(session_id, "GENERATING", 95)

            self._generate_report(session, storage_dir, analyses, consensus)

            self._progress(session_id, "COMPLETED", 100)

        except SessionCancelled:
            pass  # status is already CANCELLED; leave progress as-is

        except Exception as error:  # noqa: BLE001
            self.repo.set_session_error(session_id, str(error)[:2000])

    # ---------------------------------------------------------- analysis --

    def _analyze_document(
        self, llm, session, document_id, index, title, document_type,
        merged_path, doc_dir,
    ):
        text = merged_path.read_text(encoding="utf-8")[: self.MAX_ANALYSIS_CHARS]

        system_prompt = prompts.ANALYZE_SYSTEM_PROMPT
        user_prompt = prompts.ANALYZE_USER_TEMPLATE.format(
            title=title, document_type=document_type, text=text
        )

        parsed, run = self._call_llm(
            llm, session, document_id, "ANALYZING",
            prompts.ANALYZE_PROMPT_NAME, prompts.ANALYZE_PROMPT_VERSION,
            system_prompt, user_prompt, max_tokens=4000,
        )

        source_label = f"Source {index}: {title}"

        summary_path = doc_dir / "summary.json"
        summary_path.write_text(
            json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        (doc_dir / "facts.json").write_text(
            json.dumps(parsed.get("facts", []), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (doc_dir / "entities.json").write_text(
            json.dumps(parsed.get("entities", []), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        self.repo.update_document_summary(document_id, str(summary_path))

        for fact in parsed.get("facts", []):
            if not isinstance(fact, dict):
                continue

            self.repo.create_fact(
                session["id"], document_id,
                str(fact.get("category", "")),
                str(fact.get("subcategory", "")),
                str(fact.get("value", "")),
                float(fact.get("confidence") or 0),
                str(fact.get("evidence", "")),
                str(fact.get("stage", "")),
                source_label,
            )

        for entity in parsed.get("entities", []):
            if not isinstance(entity, dict):
                continue

            self.repo.create_entity(
                session["id"], document_id,
                str(entity.get("name", "")),
                str(entity.get("type", "")),
                str(entity.get("category", "")),
                float(entity.get("confidence") or 0),
                str(entity.get("evidence", "")),
            )

        return parsed

    def _build_consensus(self, llm, session, analyses):
        blocks = []

        for item in analyses:
            analysis = item["analysis"]

            block = [f"--- Source {item['index']}: {item['title']} ---"]
            block.append(f"Summary: {analysis.get('summary', '')}")

            facts = analysis.get("facts", [])[:15]

            if facts:
                block.append("Key facts:")

                for fact in facts:
                    if isinstance(fact, dict):
                        block.append(
                            f"- [{fact.get('category', '')}] "
                            f"{fact.get('value', '')}"
                        )

            blocks.append("\n".join(block))

        user_prompt = prompts.CONSENSUS_USER_TEMPLATE.format(
            topic=session["input_value"],
            sources_block="\n\n".join(blocks)[: self.MAX_ANALYSIS_CHARS],
        )

        parsed, run = self._call_llm(
            llm, session, None, "COMPARING",
            prompts.CONSENSUS_PROMPT_NAME, prompts.CONSENSUS_PROMPT_VERSION,
            prompts.CONSENSUS_SYSTEM_PROMPT, user_prompt, max_tokens=4000,
        )

        self.repo.create_consensus(
            session["id"],
            json.dumps(parsed.get("common_practices", []), ensure_ascii=False),
            json.dumps(parsed.get("differences", []), ensure_ascii=False),
            json.dumps(parsed.get("conflicting_advice", []), ensure_ascii=False),
            json.dumps(parsed.get("recommendation", {}), ensure_ascii=False),
            float(parsed.get("confidence") or 0),
        )

        return parsed

    def _call_llm(
        self, llm, session, document_id, stage,
        prompt_name, prompt_version, system_prompt, user_prompt, max_tokens,
    ):
        temperature = float(session.get("temperature") or 0.2)
        max_tokens = int(session.get("max_tokens") or max_tokens)

        try:
            parsed, result = llm.generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=session["ai_model"],
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception:
            self.repo.create_ai_run(
                session["id"], document_id, stage,
                llm.provider_name, session["ai_model"],
                prompt_name, prompt_version,
                LLMService.hash_text(system_prompt),
                LLMService.hash_text(user_prompt),
                temperature, max_tokens, 0, 0, 0.0, 0, "FAILED",
            )
            raise

        self.repo.create_ai_run(
            session["id"], document_id, stage,
            llm.provider_name, result.model,
            prompt_name, prompt_version,
            LLMService.hash_text(system_prompt),
            LLMService.hash_text(user_prompt),
            temperature, max_tokens,
            result.input_tokens, result.output_tokens,
            result.estimated_cost, result.latency_ms, "SUCCESS",
        )

        return parsed, result

    # ------------------------------------------------------------ report --

    def _generate_report(self, session, storage_dir, analyses, consensus):
        session_id = session["id"]

        facts = self.repo.list_facts_by_session(session_id)
        entities = self.repo.list_entities_by_session(session_id)

        primary = analyses[0]["analysis"]

        if consensus:
            executive_summary = consensus.get("executive_summary", "")
            recommendation = consensus.get("recommendation", {})
            timeline = consensus.get("timeline", []) or primary.get("timeline", [])
            conflicts = consensus.get("conflicting_advice", [])
        else:
            executive_summary = primary.get("summary", "")
            recommendation = {
                "summary": "",
                "steps": primary.get("recommendations", []),
                "rationale": "",
            }
            timeline = primary.get("timeline", [])
            conflicts = []

        report = {
            "session_id": session_id,
            "mode": session["mode"],
            "input_value": session["input_value"],
            "source_type": session["source_type"],
            "ai_provider": session["ai_provider"],
            "ai_model": session["ai_model"],
            "pipeline_version": session["pipeline_version"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "executive_summary": executive_summary,
            "consensus": consensus,
            "recommendation": recommendation,
            "timeline": timeline,
            "conflicts": conflicts,
            "documents": [
                {
                    "index": item["index"],
                    "document_id": item["document_id"],
                    "title": item["title"],
                    "url": item["url"],
                    "summary": item["analysis"].get("summary", ""),
                    "recommendations": item["analysis"].get("recommendations", []),
                    "warnings": item["analysis"].get("warnings", []),
                    "mistakes": item["analysis"].get("mistakes", []),
                }
                for item in analyses
            ],
            "facts": facts,
            "entities": entities,
        }

        report_path = storage_dir / "report.json"
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        markdown_path = storage_dir / "report.md"
        markdown_path.write_text(
            self._render_markdown(report), encoding="utf-8"
        )

        self.repo.set_session_report(
            session_id, str(report_path), str(markdown_path)
        )

    @staticmethod
    def _render_markdown(report):
        lines = [
            f"# Knowledge Research Report - {report['input_value']}",
            "",
            f"*Mode: {report['mode']} | Sources: {len(report['documents'])} | "
            f"Model: {report['ai_model']} | Pipeline: {report['pipeline_version']} | "
            f"Generated: {report['generated_at']}*",
            "",
            "## Executive Summary",
            "",
            report["executive_summary"] or "_No summary produced._",
            "",
        ]

        consensus = report.get("consensus")

        if consensus:
            lines += ["## Consensus", ""]

            for practice in consensus.get("common_practices", []):
                if isinstance(practice, dict):
                    supported = ", ".join(practice.get("supported_by", []))
                    lines.append(
                        f"- **{practice.get('practice', '')}** "
                        f"(confidence {practice.get('confidence', 0)}; {supported})"
                    )

            lines.append("")

            differences = consensus.get("differences", [])

            if differences:
                lines += ["### Differences Between Sources", ""]

                for diff in differences:
                    if isinstance(diff, dict):
                        lines.append(f"- **{diff.get('aspect', '')}**")

                        for pos in diff.get("positions", []):
                            if isinstance(pos, dict):
                                lines.append(
                                    f"  - {pos.get('source', '')}: "
                                    f"{pos.get('position', '')}"
                                )

                lines.append("")

        conflicts = report.get("conflicts", [])

        if conflicts:
            lines += ["## Conflicting Advice", ""]

            for conflict in conflicts:
                if isinstance(conflict, dict):
                    sources = ", ".join(conflict.get("sources", []))
                    lines.append(
                        f"- **{conflict.get('topic', '')}**: "
                        f"{conflict.get('conflict', '')} ({sources})"
                    )

            lines.append("")

        recommendation = report.get("recommendation", {})

        if recommendation and (
            recommendation.get("summary") or recommendation.get("steps")
        ):
            lines += ["## Recommendation", ""]

            if recommendation.get("summary"):
                lines += [recommendation["summary"], ""]

            for step_index, step in enumerate(recommendation.get("steps", []), 1):
                lines.append(f"{step_index}. {step}")

            if recommendation.get("rationale"):
                lines += ["", f"*Rationale: {recommendation['rationale']}*"]

            lines.append("")

        timeline = report.get("timeline", [])

        if timeline:
            lines += ["## Timeline", ""]

            for entry in timeline:
                if isinstance(entry, dict):
                    timing = f" ({entry['timing']})" if entry.get("timing") else ""
                    lines.append(
                        f"{entry.get('step', '')}. **{entry.get('label', '')}**"
                        f"{timing} - {entry.get('detail', '')}"
                    )

            lines.append("")

        lines += ["## Sources", ""]

        for document in report["documents"]:
            lines += [
                f"### Source {document['index']}: {document['title']}",
                "",
                document["url"],
                "",
                document["summary"],
                "",
            ]

            if document["warnings"]:
                lines.append("**Warnings:** " + "; ".join(document["warnings"]))
                lines.append("")

        facts = report.get("facts", [])

        if facts:
            lines += [
                "## Extracted Facts",
                "",
                "| Category | Subcategory | Value | Confidence | Source |",
                "|---|---|---|---|---|",
            ]

            for fact in facts:
                lines.append(
                    f"| {fact.get('category', '')} | {fact.get('subcategory', '')} "
                    f"| {fact.get('value', '')} | {fact.get('confidence', '')} "
                    f"| {fact.get('source_document', '')} |"
                )

            lines.append("")

        entities = report.get("entities", [])

        if entities:
            lines += [
                "## Entities",
                "",
                "| Entity | Type | Category | Confidence |",
                "|---|---|---|---|",
            ]

            for entity in entities:
                lines.append(
                    f"| {entity.get('entity_name', '')} | {entity.get('entity_type', '')} "
                    f"| {entity.get('category', '')} | {entity.get('confidence', '')} |"
                )

            lines.append("")

        return "\n".join(lines)

    # ------------------------------------------------------------- utils --

    def _progress(self, session_id, stage, percent):
        # Every progress update doubles as a cancellation checkpoint, so a
        # cancelled session stops at the next stage boundary and no update
        # ever overwrites the CANCELLED status.
        self._check_cancelled(session_id)

        status = stage if stage in ("COMPLETED", "FAILED") else "RUNNING"
        self.repo.update_session_progress(session_id, status, stage, percent)

    def _check_cancelled(self, session_id):
        session = self.repo.get_session(session_id)

        if session and session["status"] == "CANCELLED":
            raise SessionCancelled()

    @staticmethod
    def _read_json(path):
        if not path:
            return None

        file = Path(path)

        if not file.exists():
            return None

        try:
            return json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
