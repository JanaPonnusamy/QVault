from dataclasses import dataclass


@dataclass
class SearchSource:
    document_type: str
    source_reference: str
    title: str
    url: str
