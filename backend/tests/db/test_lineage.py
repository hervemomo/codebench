"""Walking parent_run_id reconstructs the checkpoint lineage (notebook 0-G,
now a DB chain instead of pickles). The actual split/merge *operations* are
implemented in codeframe (Sequence 1) and wired to the API in Sequences 4/5;
here we only verify the CodingRun chain itself is queryable end to end.
"""

from app.models import CodingRunKind
from tests.db.factories import CodingRunFactory


def test_split_then_merge_chain_lineage_reconstructs_history(db_session):
    s2 = CodingRunFactory(kind=CodingRunKind.S2, parent_run_id=None)
    db_session.flush()

    split = CodingRunFactory(kind=CodingRunKind.SPLIT, question=s2.question, parent_run_id=s2.id)
    db_session.flush()

    merge = CodingRunFactory(kind=CodingRunKind.MERGE, question=s2.question, parent_run_id=split.id)
    db_session.flush()

    # Walk parent_run_id from the tip back to the root.
    chain = [merge]
    current = merge
    while current.parent_run_id is not None:
        current = db_session.get(type(current), current.parent_run_id)
        chain.append(current)

    lineage_ids = [r.id for r in chain]
    assert lineage_ids == [merge.id, split.id, s2.id]
    assert [r.kind for r in reversed(chain)] == [CodingRunKind.S2, CodingRunKind.SPLIT, CodingRunKind.MERGE]
    assert chain[-1].parent_run_id is None


def test_multiple_children_can_share_a_parent(db_session):
    s2 = CodingRunFactory(kind=CodingRunKind.S2, parent_run_id=None)
    db_session.flush()

    split_a = CodingRunFactory(kind=CodingRunKind.SPLIT, question=s2.question, parent_run_id=s2.id)
    split_b = CodingRunFactory(kind=CodingRunKind.SPLIT, question=s2.question, parent_run_id=s2.id)
    db_session.flush()

    assert {split_a.parent_run_id, split_b.parent_run_id} == {s2.id}
    assert split_a.id != split_b.id
