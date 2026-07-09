import numpy as np

from codeframe.clustering import discover_themes, embed


def test_embed_returns_one_vector_per_text(fake_client, project_cfg):
    texts = ["great taste", "good price", "nice packaging", "always available", "good energy"]

    emb = embed(texts, project_cfg, fake_client)

    assert emb.shape[0] == len(texts)
    assert emb.ndim == 2


def test_embed_is_deterministic_across_calls(fake_client, project_cfg):
    texts = ["great taste today", "great taste today"]

    emb = embed(texts, project_cfg, fake_client)

    assert np.array_equal(emb[0], emb[1])


def test_discover_themes_is_deterministic(fake_client, project_cfg, cluster_cfg, sample_texts):
    embeddings = embed(sample_texts, project_cfg, fake_client)

    result_1 = discover_themes(embeddings, sample_texts, cluster_cfg)
    result_2 = discover_themes(embeddings, sample_texts, cluster_cfg)

    assert result_1.labels.tolist() == result_2.labels.tolist()


def test_discover_themes_finds_multiple_clusters(fake_client, project_cfg, cluster_cfg, sample_texts):
    embeddings = embed(sample_texts, project_cfg, fake_client)

    result = discover_themes(embeddings, sample_texts, cluster_cfg)

    assert len(result.representatives) >= 2
    for reps in result.representatives.values():
        assert 1 <= len(reps) <= cluster_cfg.representatives


def test_discover_themes_requires_minimum_responses(fake_client, project_cfg, cluster_cfg):
    texts = ["short text"] * 5
    embeddings = embed(texts, project_cfg, fake_client)

    try:
        discover_themes(embeddings, texts, cluster_cfg)
        raised = False
    except ValueError:
        raised = True
    assert raised
