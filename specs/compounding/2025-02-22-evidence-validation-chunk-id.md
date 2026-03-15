# Evidence validation should anchor to stored chunks

## Context
We tightened evidence validation to require quote + page + chunk_id and to ensure the quote is a verbatim substring of the retrieved chunk. This surfaced that proposals can look plausible while being ungrounded in retrieved text.

## Lesson
When an extraction pipeline uses retrieval for grounding, **validation must check that evidence quotes are anchored to a stored chunk**. Without the chunk linkage, proposals can silently drift away from retrieved evidence, even if quotes look reasonable.

## Impact
- Ensures proposals are either fully grounded or explicitly marked unclear.
- Makes evidence debugging deterministic by tying every quote to a stored chunk ID.

## Possible durable rule
If evidence is required, **reject any proposal that lacks a chunk_id or whose quote is not a verbatim substring of the chunk text**, and log validation errors for review.
