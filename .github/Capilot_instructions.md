Copilot Instructions for Entelgia
These instructions guide AI coding assistants working in this repository. They apply to pull request review, code suggestions, code generation, and repository-aware chat.

The most important rule is:

Preserve Entelgia’s architecture. Do not flatten, simplify away, or merge core systems unless explicitly asked.

1. Project Identity
Entelgia is an experimental cognitive dialogue architecture, not a generic chatbot wrapper.

It explores how internal structure affects agent behavior over time through:

persistent memory
emotional modulation
observer feedback
conflict monitoring
structured multi-agent dialogue
optional web research injection
The system should be treated as a modular cognitive architecture with interacting subsystems.

2. Core Architectural Principle
Entelgia is built around separation of responsibilities.

When reviewing or editing code:

preserve module boundaries
avoid tight coupling
avoid moving logic into unrelated files
avoid “quick fixes” that bypass architecture
prefer small patches over broad refactors
Do not collapse multiple systems into one procedural block just because it is shorter.

3. Main Agents
Socrates
Purpose:

philosophical inquiry
probing hidden assumptions
reflective questioning
epistemic exploration
Typical behavior:

asks questions
reframes concepts
deepens ambiguity
challenges certainty
Athena
Purpose:

integration
synthesis
alternative interpretation
structured reasoning
Typical behavior:

connects ideas
adds conceptual depth
provides constructive disagreement
builds coherent explanations
Fixy
Purpose:

observer / regulator / mediator
Responsibilities:

detect conflict without resolution
detect loops / drift / repetition
identify structural or logical problems
intervene when dialogue quality degrades
redirect, synthesize, or stabilize the dialogue
Fixy should remain distinct from dialogue generation. Fixy is not just another speaker. Fixy is a meta-regulator.

4. Core Modules and Responsibilities
MemoryCore
Responsible for:

short-term memory
long-term conscious memory
long-term subconscious memory
promotion logic
persistence
retrieval
Important constraints:

not every stored item is consciously available
promotion from short-term to long-term should remain selective
memory logic should stay centralized here
Do not move memory promotion logic into unrelated modules.

EmotionCore
Responsible for:

emotional tagging
emotional intensity
importance signaling
modulation of downstream behavior
Emotion is not decorative metadata. Emotion affects routing, salience, and storage.

BehaviorCore
Responsible for:

rule enforcement
self-regulation
ethical / consistency constraints
behavioral shaping
Do not turn BehaviorCore into a duplicate of prompt text. It should remain a decision-affecting subsystem.

LanguageCore
Responsible for:

prompt shaping
language formatting
discourse framing
response structure support
Do not overload LanguageCore with memory or behavior logic.

ConsciousCore
Responsible for:

awareness-related state
internal pressure
conflict representation
reflective / meta-cognitive signals
ego / superego related variables where applicable
Do not reduce ConsciousCore to a logger. It represents internal state relevant to dialogue evolution.

Observer / Fixy-related logic
Responsible for:

dialogue monitoring
synthesis triggers
conflict mediation
structural correction
This logic should remain distinct from ordinary agent response generation.

5. Dialogue Flow
The expected high-level flow is:

choose active speaker
build prompt context
retrieve relevant memory
include internal state
optionally include research context
call LLM
post-process response
update state
store memory
evaluate need for Fixy intervention
continue loop
When modifying code, preserve this flow unless explicitly asked to redesign it.

6. Memory Model
Entelgia uses layered memory.

Typical layers include:

short-term memory
long-term conscious memory
long-term subconscious memory
Memory behavior may include:

promotion by importance threshold
promotion by emotional intensity
resurfacing through reflection or dreaming
suppressed / unresolved content
Important:

memory should be traceable
storage should remain interpretable
long-term memory should not become an unfiltered dump unless explicitly intended
7. Observer / Intervention Logic
Fixy or equivalent observer logic may intervene when dialogue quality degrades.

Examples of valid intervention triggers:

high conflict with no resolution
repetitive looping
drift without progress
unresolved accumulation
need for synthesis
need to question a hidden assumption
When editing intervention logic:

prefer targeted rules
avoid constant intervention
preserve cooldowns / gating
keep interventions meaningful and sparse
Fixy should improve the dialogue, not dominate it.

8. Web Research Pipeline
Web research is optional and gated.

Expected pipeline:

detect trigger
check cooldown / gating
build query
sanitize query
perform search
fetch pages
summarize / compress
inject research context into next prompt
When editing this system:

preserve cooldown behavior
preserve trigger gating
prefer compact concept-based queries
prevent prompt-template leakage into search queries
do not let research dominate every turn
Research should augment reasoning, not replace it.

9. Query Rewriting Rules
Search queries should be:

compact
concept-based
3–6 meaningful terms when possible
free of filler words
free of prompt scaffolding leakage
Avoid terms that come from template structure rather than meaning, such as:

style
drives
seed
recent
thoughts
answer
analysis
synthesis
deconstruction
Prefer:

nouns
philosophical concepts
topic-bearing terms
semantically meaningful tokens
If there is no valid trigger, do not generate a forced query.

10. What Not to Do
When suggesting code changes, do not:

flatten architecture into one giant file
merge core subsystems unnecessarily
bypass Fixy by inserting direct output hacks
move memory logic into prompt-building code
move behavior rules into emotion code
remove logging or traceability without reason
replace modular logic with hidden side effects
introduce architecture-breaking shortcuts just to satisfy tests
silently change public interfaces unless explicitly requested
11. Preferred Change Style
Prefer:

minimal patches
explicit reasoning
local changes
stable interfaces
readable diffs
preserving existing naming unless clearly wrong
preserving working pipeline behavior
If a change touches multiple modules, explain why.

If a simpler fix exists, choose it.

12. Testing Expectations
When modifying code, preserve or improve testability.

Prefer adding or updating tests for:

edge cases
routing logic
intervention triggers
search query rewriting
cooldown behavior
memory promotion logic
output post-processing
Do not remove failing tests just to make CI pass.

13. Logging and Observability
Entelgia values traceability.

Preserve logging around:

session start
agent turns
intervention triggers
topic transitions
search trigger / query / fetch / injection
memory updates where relevant
periodic processes
Avoid duplicate logging handlers. Avoid noisy logs unless debug mode is enabled.

14. Performance and Safety Constraints
Be careful with:

long-running turns
repeated web search
runaway prompt growth
uncontrolled token expansion
repeated similar outputs
unnecessary disk writes
Preserve configuration-based controls such as:

timeout handling
debug mode
research cooldown
max search results
memory thresholds
Do not remove safeguards unless explicitly requested.

15. Documentation Rules
When updating docs:

describe the real architecture, not a simplified fantasy version
do not oversell smaller models if they do not perform well enough
distinguish between “can run” and “recommended”
use precise language about limitations
keep claims consistent with actual runtime behavior
For model guidance:

prefer phrasing like “Phi-3 class or stronger recommended” if smaller models do not reliably sustain the architecture
16. Review Mode Instructions
When reviewing a PR in this repository, prioritize:

architecture preservation
module responsibility correctness
unintended coupling
hidden regressions
dialogue stability
memory / intervention correctness
search pipeline correctness
logging and observability
backward compatibility
Flag changes that:

weaken modularity
bypass observer logic
degrade search quality
silently alter dialogue flow
collapse internal state into plain prompt text
17. If You Are Unsure
If uncertain, do this in order:

explain the existing data flow
identify the narrowest safe change
propose a minimal patch
mention risks explicitly
Do not guess architecture changes casually.

18. Preferred Copilot Behavior
For this repository, AI assistants should behave as:

conservative with architecture
explicit about assumptions
patch-oriented rather than rewrite-oriented
aware of subsystem boundaries
careful with emergent behavior systems
The best suggestion is usually the smallest correct one.

19. Short Repository Summary
Entelgia is a multi-agent cognitive dialogue architecture with:

Socrates
Athena
Fixy
MemoryCore
EmotionCore
BehaviorCore
LanguageCore
ConsciousCore
observer/intervention logic
optional web research
logging / traceability
Treat it as a living architecture, not a generic chat app.
