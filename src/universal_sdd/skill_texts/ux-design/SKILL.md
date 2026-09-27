---
name: ux-design
description: Define page states, copy, and accessibility before UI implementation. Use when a feature has a screen, empty state, or user-facing message. Reviewers check the contract; they do not restyle the product.
---

# UX Design

## Goal
A screen spec the implementer can build without inventing chrome, copy, or error text.

## Directory map
- Feature field: `ux_contract` in the spec bundle and `spec.md`
- Human projection: `.sdd/docs/HLD.md` and the feature spec
- Existing screens: `graphify query "page <name>"` before drawing a new one

## Required section per surface
- Purpose and the single primary action
- Entry points and where the user goes next
- States: empty, loading, error, success, unauthorized
- Exact strings for title, helper, and error when the copy is user-facing
- Accessibility: accessible name, keyboard path, contrast expectation, live region if the state updates without navigation
- Trust text when the surface calls a model provider (what is sent, what stays local)

## Procedure
1. Tie the surface to a requirement id.
2. Write the five states even if some are one line.
3. Put the text in `ux_contract`. Implementation copies those strings.
4. Add a test or snapshot note in the test matrix for empty and error.
5. Do not specify pixel values unless an existing design token requires them.

## Checklist
- [ ] Empty and error states exist
- [ ] Primary action is named
- [ ] Copy that the user reads is written out
- [ ] Non-goals say which screens this feature will not add

## Failure modes
- Review loops about contrast or toast copy after the acceptance criterion is already tested.
- A page that only documents the happy path.
- Inventing a navigation model that contradicts the approved information architecture.

## Example
Notes list. Primary action: create. Empty: "No notes yet" plus the create control. Error: "Could not load notes" with retry. Loading: a status message, not a blank page. Unauthorized: redirect to sign-in, no note data in the response.
