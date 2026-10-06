"""Static Mermaid architecture diagram for the recommender evaluation workbench."""
from __future__ import annotations

import html
import json


def mermaid_source() -> str:
    """Return the shared data-to-evaluation flow and all ten prototype names."""
    return """flowchart TB
    catalog["Seeded PostgreSQL catalog"] --> adapters["Catalog adapter + multilingual embeddings"]
    events["Seeded CDP event history"] --> adapters
    adapters --> split["Shared Temporal holdout"]

    subgraph prototypes["Ten recommender architecture prototypes"]
        random["Random baseline"]
        popularity["Global popularity"]
        seasonal["Destination-season popularity"]
        structured["Structured content"]
        embedding["Multilingual embedding"]
        itemcf["Item-item collaborative filtering"]
        als["Implicit ALS"]
        pagerank["Personalized PageRank"]
        markov["Markov sequence"]
        hybrid["Contextual hybrid"]
    end

    split --> random
    split --> popularity
    split --> seasonal
    split --> structured
    split --> embedding
    split --> itemcf
    split --> als
    split --> pagerank
    split --> markov
    split --> hybrid

    random --> eligible["Shared eligibility + unseen-item filter"]
    popularity --> eligible
    seasonal --> eligible
    structured --> eligible
    embedding --> eligible
    itemcf --> eligible
    als --> eligible
    pagerank --> eligible
    markov --> eligible
    hybrid --> eligible

    eligible --> topk["Top-K ranked results"]
    split --> targets["Held-out purchase targets"]
    topk --> metrics["Recall@10 / Recall@20 / NDCG@10 + coverage, availability, cross-category, p95 / p99"]
    targets --> metrics
    topk --> explorer["Persona explorer"]
    metrics --> batch["Batch comparison"]
    batch --> reports["CSV / JSON reports"]
"""


def render_mermaid_html(source: str) -> str:
    """Build an iframe document with a CDN renderer and a readable source fallback."""
    source_literal = json.dumps(source, ensure_ascii=False).replace("</", "<\\/")
    fallback = html.escape(source)
    return f"""<!doctype html>
<html lang="vi">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {{ color-scheme: light dark; }}
    body {{ font: 14px/1.5 system-ui, sans-serif; margin: 0; padding: 16px; }}
    #diagram {{ display: flex; justify-content: center; overflow: auto; }}
    #diagram svg {{ max-width: 100%; height: auto; }}
    #fallback {{ color: #64748b; font-size: 12px; overflow-wrap: anywhere; }}
    #fallback pre {{ white-space: pre-wrap; }}
  </style>
</head>
<body>
  <div id="diagram" role="img" aria-label="Kiến trúc evaluation 10 recommender"></div>
  <details id="fallback">
    <summary>Không tải được Mermaid renderer? Xem mã sơ đồ</summary>
    <pre>{fallback}</pre>
  </details>
  <script type="module">
    const source = {source_literal};
    try {{
      const {{ default: mermaid }} = await import(
        "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs"
      );
      mermaid.initialize({{ startOnLoad: false, securityLevel: "strict", theme: "neutral" }});
      const {{ svg }} = await mermaid.render("recsys-architecture", source);
      document.getElementById("diagram").innerHTML = svg;
      document.getElementById("fallback").hidden = true;
    }} catch (error) {{
      document.querySelector("#fallback summary").textContent =
        "Mermaid chưa tải được; xem mã sơ đồ bên dưới";
      document.getElementById("fallback").open = true;
    }}
  </script>
</body>
</html>"""
