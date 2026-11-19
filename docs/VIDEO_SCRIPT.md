# Video script - Urban Air Quality Assistant

Target length: 2-3 minutes. Screen capture of the local app at
http://localhost:8000.

## 0:00 - 0:20 - The problem

"Northern cities spend weeks inside during winter smog. Generic advice does
not account for your city, your commute or whether you cook with LPG or wood.
This assistant turns your profile into a quantified plan."

## 0:20 - 0:50 - Register and set a profile

1. Register with an email and a password; the app stores a PBKDF2 hash and
   returns an HMAC bearer token.
2. Open the profile form. Pick a city, household flags, commute mode and
   distance, cooking fuel, heating and budget. Save.

## 0:50 - 1:30 - Read the plan

"The plan has three ranked sections: low-emission routines, indoor air hacks
and sustainable alternatives. Each card shows the weekly CO2e reduction, the
exposure reduction and the monthly cost delta, computed from a cited factor
table. The impact panel summarises the strongest routine."

## 1:30 - 2:10 - Ask a grounded question

Type a question, optionally toggle plain language, and submit.

Sample queries to show:

- "Which indoor air purifier should I use?"
- "How can I reduce kitchen smoke?"
- "Is it safe to exercise outdoors today?"
- "What is a cleaner alternative to burning wood?"

"The answer cites the corpus. Ask something outside the corpus and the
assistant refuses rather than inventing a citation."

## 2:10 - 2:40 - Add a document

"Upload a PDF - the text is extracted, chunked and added to your private
corpus. Documents are owner-scoped, so another account can never retrieve
them."

## 2:40 - 3:00 - Wrap up

"Export the plan as Markdown, or deploy the same image to Render. The whole
gate - ruff, mypy, 246 tests, 95% coverage - runs locally with one command."
