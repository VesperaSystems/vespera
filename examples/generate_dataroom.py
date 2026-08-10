"""Generate the synthetic sample dataroom.

All companies, people, and agreements in these documents are fictional and were
created solely to demonstrate Vespera. Run from the repo root:

    python examples/generate_dataroom.py
"""

from pathlib import Path

import pymupdf

OUT = Path(__file__).parent / "sample-dataroom"

MSA = """MASTER SERVICES AGREEMENT

This Master Services Agreement (the "Agreement") is entered into as of 12 March 2025
(the "Effective Date") by and between:

(1) Northgate Robotics Ltd, a company incorporated in England and Wales with company
number 09876543, whose registered office is at 14 Foundry Lane, Sheffield S1 4QT
("Northgate"); and

(2) Halcyon Data Services GmbH, a company incorporated in Germany, registered with the
commercial register of Berlin under HRB 224466, whose registered office is at
Torstrasse 88, 10119 Berlin ("Halcyon").

1. SERVICES. Halcyon shall provide the data processing and hosting services described
in Schedule A (Services) and Schedule B (Service Levels).

2. TERM. This Agreement commences on the Effective Date and continues for an initial
term of three (3) years, renewing automatically for successive one-year periods unless
either party gives ninety (90) days' written notice of non-renewal.

3. TERMINATION. Northgate may terminate this Agreement for convenience at any time on
thirty (30) days' written notice. Either party may terminate immediately on written
notice if the other party commits a material breach which is not remedied within
fourteen (14) days.

4. CHANGE OF CONTROL. If Northgate undergoes a Change of Control (meaning any transfer
of more than fifty percent (50%) of its voting shares), Halcyon may terminate this
Agreement immediately upon written notice and all outstanding fees for the remainder of
the then-current term shall become immediately due and payable.

5. ASSIGNMENT. Neither party may assign this Agreement without the prior written
consent of the other party, except that Halcyon may assign to an affiliate.

6. LIABILITY. Halcyon's aggregate liability under this Agreement is capped at the fees
paid in the twelve (12) months preceding the claim. NOTHING IN THIS CLAUSE LIMITS
NORTHGATE'S LIABILITY, WHICH SHALL BE UNLIMITED IN RESPECT OF ANY BREACH OF CLAUSE 8.

7. GOVERNING LAW. This Agreement is governed by the laws of England and Wales, and the
parties submit to the exclusive jurisdiction of the courts of England and Wales.

8. CONFIDENTIALITY. Each party shall keep confidential all Confidential Information of
the other party and use it solely for the purposes of this Agreement.

SIGNED for and on behalf of Northgate Robotics Ltd:

Name: Eleanor Vance
Title: Chief Executive Officer
Date: 12 March 2025

SIGNED for and on behalf of Halcyon Data Services GmbH:

Name: Jurgen Kessler
Title: Geschaftsfuhrer
Date: 12 March 2025
"""

SUPPLY = """EXCLUSIVE SUPPLY AGREEMENT

This Exclusive Supply Agreement is made on 2 June 2024 between:

(1) Northgate Robotics Limited ("Buyer"), of 14 Foundry Lane, Sheffield; and

(2) Kestrel Precision Components S.p.A. ("Supplier"), of Via Lambrate 12, Milan, Italy.

1. EXCLUSIVITY. During the Term, Buyer shall purchase one hundred percent (100%) of its
requirements for servo actuators exclusively from Supplier, and shall not purchase
equivalent components from any third party.

2. TERM. The Term begins on 1 July 2024 and ends on 30 June 2029. There is no right of
early termination for convenience by either party.

3. MINIMUM PURCHASE. Buyer commits to a minimum annual purchase volume of EUR 1,200,000.
If actual purchases fall below this amount in any contract year, Buyer shall pay
Supplier the shortfall in full.

4. PRICE REVIEW. Supplier may increase prices once per contract year by written notice,
capped at the greater of 8% or the change in the Italian producer price index.

5. GOVERNING LAW. This Agreement is governed by Italian law.

SIGNED for the Buyer:
Name: Eleanor Vance
Title: CEO, Northgate Robotics Limited
Date: 2 June 2024

SIGNED for the Supplier:
Name: Carla Bianchi
Title: Managing Director
Date: 2 June 2024
"""

CONTRACTOR = """INDEPENDENT CONTRACTOR AGREEMENT

This Agreement is made on 15 January 2025 between Northgate Robotics Ltd (the
"Company") and Tomas Rivera, an independent software engineer trading as Rivera
Embedded Consulting (the "Contractor").

1. SERVICES. The Contractor shall design and implement the firmware for the Company's
next-generation motor controller (the "NG-7 Firmware").

2. FEES. The Company shall pay the Contractor GBP 850 per day, invoiced monthly.

3. INTELLECTUAL PROPERTY. The Contractor grants the Company a non-exclusive,
royalty-free licence to use the deliverables. For the avoidance of doubt, all
intellectual property rights in the NG-7 Firmware, including source code and design
documents, are and shall remain the sole property of the Contractor.

4. CONFIDENTIALITY. The Contractor shall not disclose the Company's confidential
information to any third party.

5. TERMINATION. Either party may terminate on seven (7) days' written notice.

6. GOVERNING LAW. This Agreement is governed by the laws of England and Wales.

SIGNED for the Company:
Name: Eleanor Vance
Title: CEO
Date: 15 January 2025

SIGNED by the Contractor:
Name: Tomas Rivera
Date: 15 January 2025
"""

SHA_UNSIGNED = """SHAREHOLDERS' AGREEMENT

relating to Northgate Robotics Ltd

THIS AGREEMENT is made on 28 September 2025 between:

(1) Eleanor Vance of 3 Ashworth Gardens, Sheffield;
(2) Marcus Oyelaran of 91 Redcliffe Road, Nottingham;
(3) Foundry Ventures LLP of 2 King Street, Manchester; and
(4) Northgate Robotics Ltd (the "Company").

1. BOARD. The Board shall comprise up to five directors. Foundry Ventures LLP may
appoint one director for so long as it holds at least ten percent (10%) of the shares.

2. RESERVED MATTERS. The Company shall not, without Investor Consent: (a) issue new
shares; (b) incur borrowings exceeding GBP 250,000; (c) sell any material asset; or
(d) amend the Articles of Association.

3. DRAG ALONG. If holders of seventy-five percent (75%) of the shares accept an offer
for the entire issued share capital, all other shareholders shall be required to
accept the offer on the same terms.

4. TAG ALONG. No transfer of a controlling interest may be made unless the buyer
offers to acquire all other shares on the same terms.

5. GOVERNING LAW. This Agreement is governed by the laws of England and Wales.

SIGNED by Eleanor Vance:

Signature: _______________________
Date: _______________________

SIGNED by Marcus Oyelaran:

Signature: _______________________
Date: _______________________

SIGNED for Foundry Ventures LLP:

Signature: _______________________
Date: _______________________
"""

NDA_TXT = """MUTUAL NON-DISCLOSURE AGREEMENT

Made on 5 February 2025 between Northgate Robotics Ltd of 14 Foundry Lane, Sheffield
("Northgate") and Halcyon Data Services GmbH of Torstrasse 88, Berlin ("Halcyon").

1. Each party may disclose Confidential Information to the other for the purpose of
evaluating a potential data services partnership (the "Purpose").

2. The receiving party shall use Confidential Information solely for the Purpose and
shall protect it with at least the same care it applies to its own confidential
information, and no less than reasonable care.

3. The obligations in this Agreement last for five (5) years from the date of
disclosure.

4. Nothing in this Agreement obliges either party to enter into any further agreement.

5. This Agreement is governed by the laws of England and Wales.

Signed:
Eleanor Vance, CEO, Northgate Robotics Ltd, 5 February 2025
Jurgen Kessler, Geschaftsfuhrer, Halcyon Data Services GmbH, 5 February 2025
"""

BOARD_MINUTES = """NORTHGATE ROBOTICS LTD

MINUTES OF A MEETING OF THE BOARD OF DIRECTORS

Held at 14 Foundry Lane, Sheffield on 10 October 2025 at 10:00.

Present: Eleanor Vance (Chair), Marcus Oyelaran, Priya Nandakumar (Foundry Ventures
appointee).

1. APPROVAL OF SUPPLY ARRANGEMENTS. The Board noted that the Exclusive Supply
Agreement with Kestrel Precision Components was signed on 2 June 2024 and that the
minimum purchase commitment for the current contract year is EUR 1,500,000. The CFO
was asked to confirm the figure against the signed agreement.

2. FIRMWARE. The Board noted that the NG-7 firmware developed by Rivera Embedded
Consulting is now shipping in production units. The Chair confirmed that all
intellectual property in the firmware is owned outright by the Company.

3. FUNDRAISING. The Board resolved to proceed with the proposed Series B financing and
noted that completion is targeted for Q1 2026, subject to investor due diligence.

4. NEXT MEETING. 12 December 2025.

Approved as a true record.

Eleanor Vance, Chair
"""


LINES_PER_PAGE = 46


FINANCIALS = """NORTHGATE ROBOTICS LTD

FINANCIAL SUMMARY — FY2025 (UNAUDITED MANAGEMENT ACCOUNTS)

Prepared by the CFO office, 30 September 2025. All figures in GBP unless stated.

1. REVENUE. Total revenue for FY2025 was £12.4 million, up 46% from £8.5 million in
FY2024. Recurring software and support revenue (ARR basis) at year end was
£9.6 million.

2. GROSS MARGIN. Blended gross margin was 61%, reflecting the mix of hardware
(41% margin) and software subscriptions (84% margin).

3. OPERATING RESULT. Operating loss for FY2025 was £1.8 million, an improvement from
a £3.1 million loss in FY2024.

4. CASH. Cash at bank on 30 September 2025 was £4.2 million. At the current net burn
rate of approximately £0.35 million per month, this supports roughly 12 months of
runway before the planned Series B.

5. CUSTOMERS. The company served 86 active customers at year end, up from 61.
Net revenue retention for the software business was 117%.

6. CONCENTRATION. The three largest customers together represented 34% of FY2025
revenue.

This summary is unaudited and prepared for internal planning and investor discussions.
"""

INVESTOR_UPDATE = """NORTHGATE ROBOTICS — INVESTOR UPDATE — OCTOBER 2025

Dear investors,

Momentum has continued through the autumn. A few highlights ahead of the Series B
process:

- Annual recurring revenue has now reached £11.2 million, and we expect to cross
  £12 million ARR before the end of the calendar year.
- We added nine new enterprise logos this quarter, taking us to 95 active customers.
- The NG-7 motor controller line, powered by firmware from Rivera Embedded
  Consulting, is now shipping in production volumes.
- Gross margin continues to trend upward as software becomes a larger share of the
  mix.

We remain confident in the plan presented at the last board meeting and look forward
to sharing the full Series B materials shortly.

Eleanor Vance
CEO, Northgate Robotics Ltd
"""


PRODUCT_OVERVIEW = """NORTHGATE ROBOTICS — PRODUCT OVERVIEW

NORTHGATE PULSE: AI-POWERED PREDICTIVE MAINTENANCE

Prepared for the Series B process, October 2025.

1. OVERVIEW. Northgate Pulse is our AI-powered predictive maintenance platform,
bundled with every NG-7 motor controller. Pulse harnesses cutting-edge artificial
intelligence to anticipate failures before they happen, delivering an intelligent,
self-optimising maintenance experience for industrial customers.

2. HOW IT WORKS. Pulse monitors vibration, temperature, and current draw on each
connected actuator. When a reading exceeds the configured threshold for its device
class, Pulse raises a maintenance ticket in the customer's CMMS via our REST API.
Threshold values are set per device class at commissioning and can be adjusted by the
customer's maintenance engineer from the Pulse dashboard.

3. DEPLOYMENT. Pulse runs on our standard cloud stack (PostgreSQL, Redis, a Django
application tier) and ships with connectors for SAP PM and Fiix.

4. ROADMAP. We continue to invest in the intelligence layer of Pulse to extend our
AI leadership in the predictive maintenance category.

5. SUPPORT. Our support team handles all Pulse tickets by email and telephone with a
target first response of four business hours.
"""


def write_pdf(name: str, text: str, title: str) -> None:
    doc = pymupdf.open()
    rect = pymupdf.paper_rect("a4")
    margin = 54
    text_rect = rect + (margin, margin, -margin, -margin)
    lines = text.split("\n")
    for start in range(0, len(lines), LINES_PER_PAGE):
        page = doc.new_page(width=rect.width, height=rect.height)
        if start == 0:
            page.insert_text((margin, margin - 14), title, fontsize=8, color=(0.4, 0.4, 0.4))
        block = "\n".join(lines[start : start + LINES_PER_PAGE])
        spill = page.insert_textbox(text_rect, block, fontsize=10, fontname="helv")
        if spill < 0:
            raise RuntimeError(f"page overflow in {name}: reduce LINES_PER_PAGE")
    pages = doc.page_count
    doc.save(OUT / name)
    doc.close()
    print(f"wrote {name} ({pages} pages)")


def write_docx(name: str, text: str) -> None:
    import docx

    document = docx.Document()
    for line in text.split("\n"):
        document.add_paragraph(line)
    document.save(OUT / name)
    print(f"wrote {name}")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write_pdf("01-master-services-agreement.pdf", MSA, "Master Services Agreement — Northgate / Halcyon")
    write_pdf("02-exclusive-supply-agreement.pdf", SUPPLY, "Exclusive Supply Agreement — Northgate / Kestrel")
    write_pdf("03-contractor-agreement-firmware.pdf", CONTRACTOR, "Independent Contractor Agreement — NG-7 Firmware")
    write_pdf("04-shareholders-agreement-DRAFT.pdf", SHA_UNSIGNED, "Shareholders' Agreement — Northgate Robotics Ltd")
    write_docx("05-board-minutes-2025-10-10.docx", BOARD_MINUTES)
    (OUT / "06-mutual-nda.txt").write_text(NDA_TXT, encoding="utf-8")
    print("wrote 06-mutual-nda.txt")
    write_pdf("07-financial-summary-fy2025.pdf", FINANCIALS, "Financial Summary FY2025 — Northgate Robotics Ltd")
    (OUT / "08-investor-update-oct-2025.txt").write_text(INVESTOR_UPDATE, encoding="utf-8")
    print("wrote 08-investor-update-oct-2025.txt")
    write_pdf("09-product-overview-pulse.pdf", PRODUCT_OVERVIEW, "Northgate Pulse — Product Overview")


if __name__ == "__main__":
    main()
