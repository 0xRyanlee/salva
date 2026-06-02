# Debug Playbook

Use this when a route, provider, or pipeline behavior looks wrong.

## Step 1: identify the surface

- If the question is "what shape is this search space?", inspect the topology probe spec.
- If the question is "should we ask clarifying questions or just run?", inspect the preprompt and planner specs.
- If the question is "which pipeline should I use?", inspect the route catalog.
- If the question is "why did the result set look weak?", inspect retrieval contract and provider state.
- If the question is "why did the run not improve over time?", inspect query-family memory seeding.

## Step 2: verify the contract

- Check probe topology classification and confidence.
- Check objective -> experience profile mapping.
- Check route -> strategy rotation mapping.
- Check pilot advice for round budget, clarification mode, and stop conditions.
- Check retrieval mode and provider list.
- Check whether the result quality threshold caused parallel expansion.

## Step 3: isolate the failure

- If the issue is reproducible without network, it is usually a routing or schema problem.
- If the issue only appears with one provider, it is usually provider contract or health-state related.
- If the issue only appears after multiple runs, it is usually memory bootstrap or persistence-related.

## Step 4: decide the fix class

- Contract bug: update spec first, then code.
- Mapping bug: update route catalog or objective mapping.
- Provider bug: update provider contract or fallback logic.
- Persistence bug: update schema migration and tests.

## Minimum evidence to collect

- Probe classification and route plan
- Objective
- Route entry
- Retrieval mode
- Pilot round budget and clarification mode
- Provider list and health state
- Query family memory usage
- Any relation or run persistence collision

Related specs:

- [topology-probe.md](topology-probe.md)
- [planner.md](planner.md)
- [preprompt.md](preprompt.md)
- [route-catalog.md](route-catalog.md)
- [retrieval-contract.md](retrieval-contract.md)
