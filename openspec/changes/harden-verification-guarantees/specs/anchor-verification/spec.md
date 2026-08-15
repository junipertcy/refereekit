# Delta for anchor-verification

## MODIFIED Requirements

### Requirement: Equation anchor verification

`verify` SHALL return PASS for an equation anchor only when the anchor lies
within the contiguous run of extracted numeric ids beginning at 1. An anchor
outside that run SHALL return FAIL.

Equation ids are recovered from right-margin geometry, which is best-effort and
produces noise. PASS is an assertion the referee relies on when citing, so it
SHALL be confined to the range where extraction is trustworthy.

An anchor outside the run SHALL NOT return FLAG. FLAG admits an anchor to the
claim pool, which would leave a citation to a nonexistent equation available to
the draft — nearly as harmful as PASS, and harder to notice.

#### Scenario: An id inside the contiguous run passes
- **GIVEN** a document whose extracted numeric equation ids are 1,2,3,4,5,6,7 and 18,500
- **WHEN** an equation anchor of 7 is verified
- **THEN** the verdict is PASS

#### Scenario: An id above the contiguous run fails
- **GIVEN** the same document
- **WHEN** an equation anchor of 500 is verified
- **THEN** the verdict is FAIL
- **AND** the verdict is not FLAG, so the anchor does not enter the claim pool

#### Scenario: A gap ends the run
- **GIVEN** a document whose extracted numeric equation ids are 1,2,3 and 18,19,20
- **WHEN** an equation anchor of 18 is verified
- **THEN** the verdict is FAIL, because the run ends at 3

#### Scenario: A document with no extracted equations passes nothing
- **GIVEN** a document from which no equation id was extracted
- **WHEN** any equation anchor is verified
- **THEN** the verdict is FAIL

#### Scenario: The evidence explains a refusal outside the run
- **GIVEN** a document whose contiguous run ends at 7
- **WHEN** an equation anchor of 500 is verified
- **THEN** the evidence distinguishes "outside the range extraction can vouch for"
  from "no such equation id was found at all"

#### Scenario: Figure anchors are unaffected
- **GIVEN** figures are recovered from caption lines rather than margin geometry
- **WHEN** a figure anchor is verified
- **THEN** existence against the extracted figure list decides the verdict, as before
