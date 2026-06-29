import json

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.knowledge import KnowledgeNode
from app.repositories.document_repository import DocumentRepository
from app.repositories.knowledge_repository import KnowledgeRepository


def _snippet(text: str, length: int = 90) -> str:
    flat = " ".join(text.split())
    return flat[:length] + ("…" if len(flat) > length else "")


def _parse(extra: str) -> dict | None:
    if not extra:
        return None
    try:
        return json.loads(extra)
    except json.JSONDecodeError:
        return None


class KnowledgeMapService:
    """Deterministically map a processed document's structure into a hierarchical
    tree of knowledge nodes. No AI, no OCR — purely from extracted elements and
    bookmarks. Hierarchy comes from headings (preferred) or bookmarks (fallback);
    paragraphs/tables/figures become leaf nodes under their enclosing section."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = KnowledgeRepository(db)
        self.docs = DocumentRepository(db)

    # ---------- mapping ----------

    def map_document(self, document: Document) -> dict:
        self.repo.clear_for_document(document.id)
        elements = self.docs.elements(document.id)
        bookmarks = self.docs.bookmarks(document.id)

        self._order = 0
        root = self._node(document.id, None, "root", title=document.title or f"Document {document.id}")

        headings = [e for e in elements if e.element_type == "heading"]
        content = [e for e in elements if e.element_type != "heading"]

        if headings:
            strategy = "headings"
            stack: list[tuple[int, KnowledgeNode]] = [(0, root)]
            for el in elements:
                if el.element_type == "heading":
                    level = el.level or 1
                    while len(stack) > 1 and stack[-1][0] >= level:
                        stack.pop()
                    parent = stack[-1][1]
                    section = self._node(
                        document.id, parent, "section", title=el.text, level=level,
                        depth=parent.depth + 1, page=el.page, element_id=el.id,
                    )
                    stack.append((level, section))
                else:
                    self._leaf(document.id, stack[-1][1], el)
        elif bookmarks:
            strategy = "bookmarks"
            stack = [(0, root)]
            sections: list[tuple[int, KnowledgeNode]] = []
            for bm in bookmarks:
                while len(stack) > 1 and stack[-1][0] >= bm.level:
                    stack.pop()
                parent = stack[-1][1]
                section = self._node(
                    document.id, parent, "section", title=bm.title, level=bm.level,
                    depth=parent.depth + 1, page=bm.page,
                )
                stack.append((bm.level, section))
                sections.append((bm.page, section))
            sections.sort(key=lambda t: t[0])
            for el in content:
                parent = root
                for page, section in sections:
                    if page <= el.page:
                        parent = section
                    else:
                        break
                self._leaf(document.id, parent, el)
        else:
            strategy = "flat"
            for el in content:
                self._leaf(document.id, root, el)

        self.repo.commit()
        return {"strategy": strategy, "nodes": self._order}

    def _leaf(self, document_id: int, parent: KnowledgeNode, el) -> KnowledgeNode:
        extra = _parse(el.extra)
        if el.element_type == "table":
            n_rows = (extra or {}).get("n_rows", 0)
            n_cols = (extra or {}).get("n_cols", 0)
            title = f"Table {n_rows}×{n_cols}"
            content = ""
        elif el.element_type == "figure":
            width = (extra or {}).get("width", 0)
            height = (extra or {}).get("height", 0)
            title = f"Figure {width}×{height}"
            content = ""
        else:
            title = _snippet(el.text)
            content = el.text
        return self._node(
            document_id, parent, el.element_type, title=title, content=content,
            depth=parent.depth + 1, page=el.page, element_id=el.id, extra=extra,
        )

    def _node(
        self, document_id, parent, node_type, title="", content="", level=None,
        depth=0, page=0, element_id=None, extra=None,
    ) -> KnowledgeNode:
        node = KnowledgeNode(
            document_id=document_id,
            parent_id=parent.id if parent else None,
            node_type=node_type,
            title=(title or "")[:500],
            content=content or "",
            level=level,
            depth=depth,
            order_index=self._order,
            page=page,
            element_id=element_id,
            extra=json.dumps(extra) if extra else "",
        )
        self.repo.add(node)  # flush to assign id
        node.path = (f"{parent.path}/" if parent and parent.path else "/") + str(node.id)
        self._order += 1
        return node

    def clear(self, document_id: int) -> None:
        self.repo.clear_for_document(document_id)

    # ---------- navigation / search ----------

    def tree(self, document_id: int) -> dict | None:
        nodes = self.repo.for_document(document_id)
        if not nodes:
            return None
        by_id: dict[int, dict] = {}
        for node in nodes:
            by_id[node.id] = self._node_dict(node) | {"children": []}
        root = None
        for node in nodes:
            payload = by_id[node.id]
            if node.parent_id and node.parent_id in by_id:
                by_id[node.parent_id]["children"].append(payload)
            elif node.node_type == "root":
                root = payload
        return root

    def node_detail(self, node: KnowledgeNode) -> dict:
        ancestor_ids = [int(p) for p in node.path.split("/") if p][:-1]
        ancestors = {n.id: n for n in self.repo.get_many(ancestor_ids)}
        breadcrumb = [
            {"id": aid, "title": ancestors[aid].title} for aid in ancestor_ids if aid in ancestors
        ]
        children = self.repo.children(node.document_id, node.id)
        data = self._node_dict(node)
        data["extra"] = _parse(node.extra)
        data["breadcrumb"] = breadcrumb
        data["children"] = [self._node_dict(c) for c in children]
        return data

    def search(self, query: str, document_id: int | None, limit: int = 50) -> list[dict]:
        results = []
        doc_titles: dict[int, str] = {}
        for node in self.repo.search(query, document_id=document_id, limit=limit):
            if node.document_id not in doc_titles:
                doc = self.db.get(Document, node.document_id)
                doc_titles[node.document_id] = doc.title if doc else ""
            ancestor_ids = [int(p) for p in node.path.split("/") if p][:-1]
            ancestors = {n.id: n.title for n in self.repo.get_many(ancestor_ids)}
            results.append(
                self._node_dict(node)
                | {
                    "document_title": doc_titles[node.document_id],
                    "breadcrumb": [ancestors[a] for a in ancestor_ids if a in ancestors],
                }
            )
        return results

    @staticmethod
    def _node_dict(node: KnowledgeNode) -> dict:
        return {
            "id": node.id,
            "document_id": node.document_id,
            "parent_id": node.parent_id,
            "node_type": node.node_type,
            "title": node.title,
            "content": node.content,
            "level": node.level,
            "depth": node.depth,
            "order_index": node.order_index,
            "page": node.page,
        }
