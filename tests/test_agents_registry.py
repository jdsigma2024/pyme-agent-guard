from pyme_guard.domain.agents import AGENTS, AGENTS_BY_ID, ROLES_BY_ID


def test_ids_are_unique():
    assert len(AGENTS_BY_ID) == len(AGENTS)


def test_generative_agents_are_read_only():
    for agent in AGENTS:
        if agent.uses_llm:
            assert all(p.startswith("lectura:") for p in agent.permissions), agent.id
            assert agent.executes == (), agent.id


def test_no_agent_can_approve_or_disburse():
    for agent in AGENTS:
        joined = " ".join(agent.executes).lower()
        assert "aprob" not in joined and "desembols" not in joined, agent.id


def test_handoffs_point_to_known_humans():
    for agent in AGENTS:
        for target in agent.handoff_to:
            assert target in ROLES_BY_ID, (agent.id, target)


def test_every_agent_declares_limits_and_memory():
    for agent in AGENTS:
        assert agent.never and agent.memory and agent.goal
