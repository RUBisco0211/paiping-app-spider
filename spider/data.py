from dataclasses import asdict, dataclass

import yaml
from bs4.element import PageElement


@dataclass
class PaiAppRawData:
    title: str
    html_elements: list[PageElement] | str


@dataclass
class PaiArticleData:
    title: str
    url: str
    id: int
    release_time: str
    released_date: str


@dataclass
class PaiAppData:
    article: PaiArticleData
    file_title: str
    platforms: list[str]
    content: str
    img_list: list[str]


@dataclass
class PaiAppMdFrontmatter:
    title: str
    app_name: str
    platforms: list[str]
    keywords: list[str]

    article_title: str
    article_id: int
    article_url: str
    released_time: str

    def __yaml__(self) -> str:
        return yaml.safe_dump(
            {k: v for k, v in asdict(self).items() if v is not None},
            sort_keys=False,
            allow_unicode=True,
        ).rstrip()

    def __frontmatter__(self) -> str:
        return f"---\n{self.__yaml__()}\n---"

    def __str__(self) -> str:
        return self.__frontmatter__()
