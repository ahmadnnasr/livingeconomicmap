from __future__ import annotations
import hashlib
import html

from .models import Publication, RenderedPublication


def digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class MarkdownRenderer:
    def render(self, publication: Publication) -> RenderedPublication:
        lines = [
            f"# {publication.subject}",
            "",
            f"**As of:** {publication.as_of_date}",
            "",
            publication.executive_summary,
        ]

        for section in publication.sections:
            lines.extend(["", f"## {section.title}", "", section.summary])
            lines.extend([f"- {item}" for item in section.items])

        lines.extend([
            "",
            "---",
            f"Snapshot: `{publication.snapshot_id}`  ",
            f"Model: `{publication.model_version}`  ",
            f"Trace: `{publication.trace_id}`",
        ])
        content = "\n".join(lines)
        return RenderedPublication(
            publication_id=publication.publication_id,
            format="markdown",
            content=content,
            content_hash=digest(content),
        )


class HtmlRenderer:
    def render(self, publication: Publication) -> RenderedPublication:
        section_html = []
        for section in publication.sections:
            items = "".join(f"<li>{html.escape(item)}</li>" for item in section.items)
            severity = html.escape(section.severity)
            section_html.append(
                f"""
                <section class="section severity-{severity}">
                    <h2>{html.escape(section.title)}</h2>
                    <p>{html.escape(section.summary)}</p>
                    <ul>{items}</ul>
                </section>
                """
            )

        content = f"""
        <!doctype html>
        <html>
        <head>
          <meta charset="utf-8">
          <meta name="viewport" content="width=device-width, initial-scale=1">
          <title>{html.escape(publication.subject)}</title>
          <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.5; max-width: 760px; margin: auto; padding: 24px; }}
            .header {{ border-bottom: 1px solid #ddd; margin-bottom: 24px; }}
            .section {{ margin: 24px 0; padding: 16px; border: 1px solid #e5e5e5; border-radius: 8px; }}
            .severity-warning {{ border-left: 5px solid #c28b00; }}
            .severity-critical {{ border-left: 5px solid #b00020; }}
            .meta {{ margin-top: 32px; color: #666; font-size: 12px; }}
          </style>
        </head>
        <body>
          <div class="header">
            <h1>{html.escape(publication.subject)}</h1>
            <p><strong>As of:</strong> {html.escape(publication.as_of_date)}</p>
            <p>{html.escape(publication.executive_summary)}</p>
          </div>
          {''.join(section_html)}
          <div class="meta">
            Snapshot: {html.escape(publication.snapshot_id)}<br>
            Model: {html.escape(publication.model_version)}<br>
            Trace: {html.escape(publication.trace_id)}
          </div>
        </body>
        </html>
        """.strip()

        return RenderedPublication(
            publication_id=publication.publication_id,
            format="html",
            content=content,
            content_hash=digest(content),
        )


class JsonRenderer:
    def render(self, publication: Publication) -> RenderedPublication:
        import json
        from dataclasses import asdict
        content = json.dumps(asdict(publication), indent=2, sort_keys=True)
        return RenderedPublication(
            publication_id=publication.publication_id,
            format="json",
            content=content,
            content_hash=digest(content),
        )
