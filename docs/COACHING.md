# Source-grounded live coaching

Eligible finalized sales signals retrieve a bounded set of chunks from the active corpus before a structured coach request. The request treats transcript and knowledge text as untrusted data. Returned segment IDs and chunk IDs are validated against the supplied context; unknown citations are rejected.

Product, pricing, and competitor claims require retrieved support. When the distance threshold yields no usable evidence, the coach must mark `insufficient_evidence` and ask a clarifying question or acknowledge the gap. Citations show the exact stored text and revision, but neither a citation nor model output guarantees correctness.

Each call has trigger deduplication, one in-flight generation by default, a cooldown, and a generation token that suppresses results after stop. Coaching failures emit a recoverable warning and do not block transcript delivery. Suggestions are text only and cause no external action.
