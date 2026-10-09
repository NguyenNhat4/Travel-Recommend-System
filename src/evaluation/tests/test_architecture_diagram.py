from src.evaluation.architecture_diagram import mermaid_source, render_mermaid_html


def test_architecture_diagram_names_all_ten_recommender_methods_and_shared_flow():
    source = mermaid_source()

    for method in (
        "Random baseline",
        "Global popularity",
        "Destination-season popularity",
        "Structured content",
        "Multilingual embedding",
        "Item-item collaborative filtering",
        "Implicit ALS",
        "Personalized PageRank",
        "Markov sequence",
        "Contextual hybrid",
    ):
        assert method in source
    assert "Temporal holdout" in source
    assert "Shared eligibility" in source
    assert "Top-K ranked results" in source
    assert "Recall@10 / Recall@20 / NDCG@10" in source


def test_mermaid_iframe_has_renderer_and_static_fallback_source():
    source = "flowchart LR\n  A[Seed data] --> B[Temporal holdout]"

    html = render_mermaid_html(source)

    assert "mermaid.esm.min.mjs" in html
    assert "mermaid.initialize" in html
    assert "Temporal holdout" in html
