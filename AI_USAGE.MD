1. AI Use Declaration
AI-assisted tools were used during the project. Each use is disclosed below with the tool, task, level of reliance, and how the output was validated. All produced artefacts were reviewed, tested, and integrated by the author; no AI output was committed without inspection.

Claude Sonnet
Task: Drafting MANUAL_TEST_PLAN.md (~80 UAT cases across 14 feature areas).
Reliance: Major generation
Validation: I walked every case end-to-end in the deployed instance, adjusted expected results that did not match observed behaviour. Then I tested each case manually.
Claude Sonnet
Task: AI tools were used to identify the cause of various unresolved errors.
Reliance: Partial generation
Validation: The reason for each change was identified and then tested.

Claude Sonnet
Task: Inline completion of repetitive Django template boilerplate.
Reliance: Partial generation
Validation: No template was committed without review and a manual test.
Claude Sonnet
Task: Generating deployment Powershell Scripts.
Reliance: Partial  generation
Validation: After running the deployment script, I checked to see if the target had been achieved.
Claude Sonnet
Task: Generating every recipe, ingredient, technique data in given format.
Reliance: Major generation.
Validation: Context generated but manually added.
Claude Sonnet
Task: Drafting the Region master list (country names) used in schema.sql seeds.
Reliance: Major generation
Validation: List manually reduced to ISO-recognised country names; duplicates removed by me.
Claude Sonnet
Task: Drafting copy text for empty-state messages, error banners, and confirmation dialogs, welcoming messages across the templates.
Reliance: Major generation
Validation: I edited the tone to match the project voice.
Claude Sonnet
Task: A Docker file was generated after the dockerize process failed due to errors.
Reliance: Major generation
Validation: The purpose of each line of code has been identified and corrected.
