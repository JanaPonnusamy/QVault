import sqlite3

from app.database.database_manager import DB_PATH


class KnowledgeRepository:

    def __init__(self):
        self._ensure_schema()

    def connect(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self):
        conn = sqlite3.connect(DB_PATH)

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mode TEXT NOT NULL,
                input_value TEXT NOT NULL,
                source_count_requested INTEGER DEFAULT 1,
                source_type TEXT DEFAULT 'youtube',
                ai_provider TEXT,
                ai_model TEXT,
                status TEXT DEFAULT 'QUEUED',
                current_stage TEXT DEFAULT 'QUEUED',
                progress INTEGER DEFAULT 0,
                storage_directory TEXT,
                pipeline_version TEXT,
                report_path TEXT,
                report_markdown_path TEXT,
                error_message TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                document_type TEXT NOT NULL,
                source_reference TEXT,
                title TEXT,
                url TEXT,
                language TEXT,
                duration INTEGER DEFAULT 0,
                word_count INTEGER DEFAULT 0,
                character_count INTEGER DEFAULT 0,
                file_size INTEGER DEFAULT 0,
                checksum TEXT,
                processing_version TEXT,
                transcript_path TEXT,
                subtitle_path TEXT,
                ocr_path TEXT,
                merged_text_path TEXT,
                summary_path TEXT,
                status TEXT DEFAULT 'QUEUED',
                error_message TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (session_id) REFERENCES knowledge_sessions (id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                document_id INTEGER,
                category TEXT,
                subcategory TEXT,
                value TEXT,
                confidence REAL,
                evidence TEXT,
                stage TEXT,
                source_document TEXT,
                created_at TEXT,
                FOREIGN KEY (session_id) REFERENCES knowledge_sessions (id),
                FOREIGN KEY (document_id) REFERENCES knowledge_documents (id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                document_id INTEGER,
                entity_name TEXT,
                entity_type TEXT,
                category TEXT,
                confidence REAL,
                evidence TEXT,
                created_at TEXT,
                FOREIGN KEY (session_id) REFERENCES knowledge_sessions (id),
                FOREIGN KEY (document_id) REFERENCES knowledge_documents (id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_consensus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                common_practices_json TEXT,
                differences_json TEXT,
                conflicting_advice_json TEXT,
                recommendation_json TEXT,
                confidence REAL,
                created_at TEXT,
                FOREIGN KEY (session_id) REFERENCES knowledge_sessions (id)
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_ai_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                document_id INTEGER,
                stage TEXT,
                provider TEXT,
                model TEXT,
                prompt_name TEXT,
                prompt_version TEXT,
                system_prompt_hash TEXT,
                user_prompt_hash TEXT,
                temperature REAL,
                max_tokens INTEGER,
                input_tokens INTEGER,
                output_tokens INTEGER,
                estimated_cost REAL,
                latency_ms INTEGER,
                status TEXT,
                created_at TEXT,
                FOREIGN KEY (session_id) REFERENCES knowledge_sessions (id),
                FOREIGN KEY (document_id) REFERENCES knowledge_documents (id)
            )
            """
        )

        # Additive migrations for databases created before these columns.
        existing = {
            row[1]
            for row in conn.execute(
                "PRAGMA table_info(knowledge_sessions)"
            ).fetchall()
        }

        if "temperature" not in existing:
            conn.execute(
                "ALTER TABLE knowledge_sessions "
                "ADD COLUMN temperature REAL DEFAULT 0.2"
            )

        if "max_tokens" not in existing:
            conn.execute(
                "ALTER TABLE knowledge_sessions "
                "ADD COLUMN max_tokens INTEGER DEFAULT 4000"
            )

        conn.commit()
        conn.close()

    # ---------------------------------------------------------- sessions --

    def create_session(
        self,
        mode,
        input_value,
        source_count_requested,
        source_type,
        ai_provider,
        ai_model,
        storage_directory,
        pipeline_version,
        temperature=0.2,
        max_tokens=4000,
    ):
        conn = self.connect()

        cur = conn.execute(
            """
            INSERT INTO knowledge_sessions (
                mode, input_value, source_count_requested, source_type,
                ai_provider, ai_model, status, current_stage, progress,
                storage_directory, pipeline_version, temperature, max_tokens,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'QUEUED', 'QUEUED', 0, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                mode, input_value, source_count_requested, source_type,
                ai_provider, ai_model, storage_directory, pipeline_version,
                temperature, max_tokens,
            ),
        )

        conn.commit()
        session_id = cur.lastrowid
        conn.close()

        return session_id

    def get_session(self, session_id):
        conn = self.connect()

        row = conn.execute(
            "SELECT * FROM knowledge_sessions WHERE id = ?",
            (session_id,),
        ).fetchone()

        conn.close()

        return dict(row) if row else None

    def set_session_storage_directory(self, session_id, storage_directory):
        conn = self.connect()

        conn.execute(
            """
            UPDATE knowledge_sessions
            SET storage_directory = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (storage_directory, session_id),
        )

        conn.commit()
        conn.close()

    def update_session_progress(self, session_id, status, current_stage, progress):
        conn = self.connect()

        conn.execute(
            """
            UPDATE knowledge_sessions
            SET status = ?, current_stage = ?, progress = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (status, current_stage, progress, session_id),
        )

        conn.commit()
        conn.close()

    def set_session_report(self, session_id, report_path, report_markdown_path):
        conn = self.connect()

        conn.execute(
            """
            UPDATE knowledge_sessions
            SET report_path = ?, report_markdown_path = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (report_path, report_markdown_path, session_id),
        )

        conn.commit()
        conn.close()

    def set_session_error(self, session_id, error_message):
        conn = self.connect()

        conn.execute(
            """
            UPDATE knowledge_sessions
            SET status = 'FAILED', error_message = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (error_message, session_id),
        )

        conn.commit()
        conn.close()

    def list_sessions(
        self,
        status=None,
        topic=None,
        date_from=None,
        date_to=None,
        provider=None,
        source_type=None,
    ):
        conn = self.connect()

        clauses = []
        params = []

        if status:
            clauses.append("status = ?")
            params.append(status)

        if topic:
            clauses.append("input_value LIKE ?")
            params.append(f"%{topic}%")

        if date_from:
            clauses.append("created_at >= ?")
            params.append(date_from)

        if date_to:
            clauses.append("created_at <= ?")
            params.append(date_to)

        if provider:
            clauses.append("ai_provider = ?")
            params.append(provider)

        if source_type:
            clauses.append("source_type = ?")
            params.append(source_type)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        rows = conn.execute(
            f"""
            SELECT
                s.*,
                COALESCE(r.total_cost, 0)   AS total_cost,
                COALESCE(r.total_tokens, 0) AS total_tokens
            FROM knowledge_sessions s
            LEFT JOIN (
                SELECT
                    session_id,
                    SUM(estimated_cost) AS total_cost,
                    SUM(input_tokens + output_tokens) AS total_tokens
                FROM knowledge_ai_runs
                GROUP BY session_id
            ) r ON r.session_id = s.id
            {where}
            ORDER BY s.id DESC
            """,
            params,
        ).fetchall()

        conn.close()

        return [dict(row) for row in rows]

    def delete_session(self, session_id):
        """Remove a session and every row that references it."""
        conn = self.connect()

        for table in (
            "knowledge_ai_runs",
            "knowledge_consensus",
            "knowledge_entities",
            "knowledge_facts",
            "knowledge_documents",
        ):
            conn.execute(
                f"DELETE FROM {table} WHERE session_id = ?", (session_id,)
            )

        conn.execute(
            "DELETE FROM knowledge_sessions WHERE id = ?", (session_id,)
        )

        conn.commit()
        conn.close()

    # --------------------------------------------------------- documents --

    def create_document(self, session_id, document_type, source_reference, title, url):
        conn = self.connect()

        cur = conn.execute(
            """
            INSERT INTO knowledge_documents (
                session_id, document_type, source_reference, title, url,
                status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'QUEUED', datetime('now'), datetime('now'))
            """,
            (session_id, document_type, source_reference, title, url),
        )

        conn.commit()
        document_id = cur.lastrowid
        conn.close()

        return document_id

    def update_document_extraction(
        self,
        document_id,
        language,
        duration,
        word_count,
        character_count,
        file_size,
        checksum,
        processing_version,
        transcript_path,
        subtitle_path,
        ocr_path,
        merged_text_path,
    ):
        conn = self.connect()

        conn.execute(
            """
            UPDATE knowledge_documents
            SET language = ?, duration = ?, word_count = ?, character_count = ?,
                file_size = ?, checksum = ?, processing_version = ?,
                transcript_path = ?, subtitle_path = ?, ocr_path = ?,
                merged_text_path = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                language, duration, word_count, character_count, file_size,
                checksum, processing_version, transcript_path, subtitle_path,
                ocr_path, merged_text_path, document_id,
            ),
        )

        conn.commit()
        conn.close()

    def update_document_summary(self, document_id, summary_path):
        conn = self.connect()

        conn.execute(
            """
            UPDATE knowledge_documents
            SET summary_path = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (summary_path, document_id),
        )

        conn.commit()
        conn.close()

    def update_document_status(self, document_id, status, error_message=None):
        conn = self.connect()

        conn.execute(
            """
            UPDATE knowledge_documents
            SET status = ?, error_message = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (status, error_message, document_id),
        )

        conn.commit()
        conn.close()

    def get_document(self, document_id):
        conn = self.connect()

        row = conn.execute(
            "SELECT * FROM knowledge_documents WHERE id = ?",
            (document_id,),
        ).fetchone()

        conn.close()

        return dict(row) if row else None

    def list_documents_by_session(self, session_id):
        conn = self.connect()

        rows = conn.execute(
            "SELECT * FROM knowledge_documents WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()

        conn.close()

        return [dict(row) for row in rows]

    # -------------------------------------------------------------- facts --

    def create_fact(
        self,
        session_id,
        document_id,
        category,
        subcategory,
        value,
        confidence,
        evidence,
        stage,
        source_document,
    ):
        conn = self.connect()

        conn.execute(
            """
            INSERT INTO knowledge_facts (
                session_id, document_id, category, subcategory, value,
                confidence, evidence, stage, source_document, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                session_id, document_id, category, subcategory, value,
                confidence, evidence, stage, source_document,
            ),
        )

        conn.commit()
        conn.close()

    def list_facts_by_session(self, session_id):
        conn = self.connect()

        rows = conn.execute(
            "SELECT * FROM knowledge_facts WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()

        conn.close()

        return [dict(row) for row in rows]

    # ----------------------------------------------------------- entities --

    def create_entity(
        self,
        session_id,
        document_id,
        entity_name,
        entity_type,
        category,
        confidence,
        evidence,
    ):
        conn = self.connect()

        conn.execute(
            """
            INSERT INTO knowledge_entities (
                session_id, document_id, entity_name, entity_type, category,
                confidence, evidence, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                session_id, document_id, entity_name, entity_type, category,
                confidence, evidence,
            ),
        )

        conn.commit()
        conn.close()

    def list_entities_by_session(self, session_id):
        conn = self.connect()

        rows = conn.execute(
            "SELECT * FROM knowledge_entities WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()

        conn.close()

        return [dict(row) for row in rows]

    # --------------------------------------------------------- consensus --

    def create_consensus(
        self,
        session_id,
        common_practices_json,
        differences_json,
        conflicting_advice_json,
        recommendation_json,
        confidence,
    ):
        conn = self.connect()

        conn.execute(
            """
            INSERT INTO knowledge_consensus (
                session_id, common_practices_json, differences_json,
                conflicting_advice_json, recommendation_json, confidence, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                session_id, common_practices_json, differences_json,
                conflicting_advice_json, recommendation_json, confidence,
            ),
        )

        conn.commit()
        conn.close()

    def get_consensus_by_session(self, session_id):
        conn = self.connect()

        row = conn.execute(
            "SELECT * FROM knowledge_consensus WHERE session_id = ? ORDER BY id DESC LIMIT 1",
            (session_id,),
        ).fetchone()

        conn.close()

        return dict(row) if row else None

    # ---------------------------------------------------------- ai runs --

    def create_ai_run(
        self,
        session_id,
        document_id,
        stage,
        provider,
        model,
        prompt_name,
        prompt_version,
        system_prompt_hash,
        user_prompt_hash,
        temperature,
        max_tokens,
        input_tokens,
        output_tokens,
        estimated_cost,
        latency_ms,
        status,
    ):
        conn = self.connect()

        conn.execute(
            """
            INSERT INTO knowledge_ai_runs (
                session_id, document_id, stage, provider, model, prompt_name,
                prompt_version, system_prompt_hash, user_prompt_hash,
                temperature, max_tokens, input_tokens, output_tokens,
                estimated_cost, latency_ms, status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
            (
                session_id, document_id, stage, provider, model, prompt_name,
                prompt_version, system_prompt_hash, user_prompt_hash,
                temperature, max_tokens, input_tokens, output_tokens,
                estimated_cost, latency_ms, status,
            ),
        )

        conn.commit()
        conn.close()

    def list_ai_runs_by_session(self, session_id):
        conn = self.connect()

        rows = conn.execute(
            "SELECT * FROM knowledge_ai_runs WHERE session_id = ? ORDER BY id",
            (session_id,),
        ).fetchall()

        conn.close()

        return [dict(row) for row in rows]
