# Practical Interface Reference Log

## Reference 001 Cargo Tracking Dashboard

- Received: 6 September 2026
- Source: Product-owner supplied screenshot
- Implementation route: `/practical/portal/`
- Reference status: Deliberately adapted frontend prototype
- Backend status: Not connected
- Separate simulator login: Not implemented

## Structural elements retained

- Persistent left navigation with expandable process groups
- Cargo tracking search area
- Cargo-service shortcuts
- Reference-code and information panels
- Exchange-rate table
- Notices and activity/statistics panels
- Dense desktop dashboard layout with responsive collapse for smaller screens

## Deliberate differences

- Purple, navy, and teal simulator palette
- Original simulator wordmark rather than official branding or seals
- Fictional exchange rates, notices, and activity data
- Persistent training-only warning
- No government contact details, partner logos, application-download links, or real transaction services
- Accessible headings, labelled controls, skip navigation, and keyboard focus styling

## Current behaviour

The page is available during frontend prototyping without programme, orientation, or separate practical-login checks. Controls are visual placeholders and do not search, submit, or change backend data. Access policy and monthly-reset simulator credentials will be implemented only after the page flow and data flow are approved.

## Reference 002 Cargo Tracking Popup

- Received: 6 September 2026
- Trigger: Cargo tracking in the sidebar or Cargo services panel
- Reference status: Deliberately adapted frontend prototype
- Backend status: Search not connected

The popup retains the supplied search choices: Cargo Reference No. with MN, MSN, and HSN segments; BL Number; Container/Chassis No.; BOE Number; and DO/SR No. The simulator version uses a modal dialog, fictional-data notice, labelled controls, Reset, Search, and Close. Submitting currently displays a frontend-only status message and does not transmit data.

## Reference 003 BOE Status Popup

- Received: 6 September 2026
- Trigger: BOE status in the Cargo services panel
- Reference status: Deliberately adapted frontend prototype
- Backend status: Search not connected

The popup contains the two required search fields shown in the supplied reference: BOE Number and Importer/Exporter Code. Both fields are required. The simulator version includes explicit labels, fictional-data guidance, Reset, Search, and Close controls. Submitting displays a frontend-only status message and does not transmit data.

## Reference 004 Logged In Top Navigation

- Received: 6 September 2026
- Trigger: Logged-in simulator workspace shell
- Reference status: Deliberately adapted frontend prototype
- Backend status: Navigation placeholders only

The workspace header now includes temporary links for Cargo, Clearance, Collection, Single Window, Agent Management, e-Docs, Post Clearance Audit, AEO, More Information, and DW Service. They point to frontend sections/placeholders for now. They are not official services and will be connected to simulator workflows only after their screen and data flows are supplied.

## Reference 005 Cargo Direct Delivery

- Received: 6 September 2026
- Source: Product-owner supplied screenshot
- Implementation route: `/practical/cargo/direct-delivery/`
- Reference status: Deliberately adapted frontend prototype
- Backend status: Not connected

The Cargo workflow now includes a Sea Import > Discharge > Direct Delivery screen. It includes the submit-date range and quick filters, Manifest/BL/BOE/Declaration search fields, an empty declaration list, BOE summary fields, and a Container/Chassis list with a frontend-only Save Draft button. The page uses simulator colours and fictional-data guidance; it does not submit searches, load customs data, or save a transaction.

## Reference 006 Cargo Service Request

- Received: 6 September 2026
- Source: Product-owner supplied screenshots
- Implementation route: `/practical/cargo/service-request/`
- Reference status: Deliberately adapted frontend prototype
- Backend status: Not connected

The Service Request flow starts with the list/search page and a New action. The frontend lookup requires both BL Number and Manifest No. The demo pair `DEMO-BL-2026` and `DEMO-MAN-001` reveals fictional BL Info, Container List, D/O Information, and Service Request details. Other values show a no-match message. No customs data is queried and no transaction is saved.
