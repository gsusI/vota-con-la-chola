# Security and sensitive-reporting policy

## Supported branch

Security fixes target `main`. Public snapshots are immutable; a correction
creates a new snapshot and links the superseded artifact.

## Report privately

Use GitHub private vulnerability reporting for this repository when available.
If unavailable, open a minimal issue requesting a private contact channel. Do
not include exploit details, credentials, private data, or unsafe URLs there.

Private reporting is appropriate for:

- exposed credentials, tokens, cookies, or private keys;
- injection, unsafe file handling, dependency compromise, or publication bypass;
- private personal data in raw, generated, or public artifacts;
- a flaw that can falsely attribute actions or integrity signals to a person;
- a coordinated-harassment or retaliation risk.

Public data corrections belong in the `Data correction or attribution dispute`
issue template unless disclosure itself would create harm.

## Response targets

- acknowledgement: 3 working days;
- initial severity and containment decision: 7 working days;
- status update: at least every 14 days until closure.

No bounty is promised. Good-faith research that avoids privacy harm, service
disruption, data destruction, credential access, and public disclosure before a
fix will be treated constructively.

## Release rule

Never publish a fix artifact containing secrets or workstation-identifying
paths. Run `just privacy-check-public-artifacts`. For attribution-integrity
defects, suspend the affected public claim until corrected evidence passes the
truth and integrity-signal contracts.
