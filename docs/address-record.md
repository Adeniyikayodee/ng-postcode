# A Nigerian address record

A small JSON object for passing a Nigerian address between systems. It is built around the building postcode NIPOST issues, and it maps onto the address formats that payments, health, and web systems already use.

```json
{
  "postcode": { "code": "EK-01-A03-FK-01", "level": "building", "assigned": true, "checked_at": "2026-10-03T12:00:00Z" },
  "country": "NG",
  "state": "Ekiti",
  "lga": "Ado Ekiti",
  "locality": "Ado Ekiti",
  "street_address": "12 NTA Road",
  "location": { "lat": 7.6211, "lng": 5.2214 }
}
```

Validate a record against the [JSON Schema](schemas/address.schema.json). Only `postcode` and `country` are required, and a receiver ignores fields it does not know.

## Fields

| Field | Holds | Where it comes from |
| --- | --- | --- |
| `postcode` | A [postcode reference](schemas/postcode-reference.schema.json): the code, its level, and optionally a confidence and whether NIPOST confirmed it | A code the person gave, a location pin, or `resolve_address` |
| `country` | `NG` | Fixed |
| `state` | State name | `state_name` in NIPOST's lookup |
| `lga` | Local government area name | `lga_name` in NIPOST's lookup |
| `locality` | Town or locality name | `locality_name` in NIPOST's lookup |
| `street_address` | House number and street on one line | The person, or `recent_house_address` in NIPOST's lookup |
| `description` | What else locates the place, such as "behind Fabian Hotel" | The person |
| `location` | A point on the building, in WGS 84 decimal degrees | A location pin |

NIPOST returns the three names and the house address from lookup level 2, which needs a key granted that level. These libraries hold no tables of names, so leave a name out when you have not looked it up.

## Rules

- **Send the code at the level you know:** an area or district code with its `level` is more useful to the receiver than a building code that was guessed.
- **Write the hyphenated form:** `EK-01-A03-FK-01` in a record or a message, and the compact `EK01A03FK01` in a database column.
- **Fill another format's postcode field only at building level:** a coarser code is a prefix of a postcode. Keep it in the record and leave the other format's field empty.
- **Treat it as personal data:** an address tied to a person is covered by the Nigeria Data Protection Act.

## Mapping to other formats

| Record | ISO 20022 `PstlAdr` | FHIR `Address` | schema.org `PostalAddress` | vCard `ADR` |
| --- | --- | --- | --- | --- |
| `postcode.code` | `PstCd` | `postalCode` | `postalCode` | postal code |
| `country` | `Ctry` | `country` | `addressCountry` | country name |
| `state` | `CtrySubDvsn` | `state` | `addressRegion` | region |
| `lga` | `DstrctNm` | `district` | none | none |
| `locality` | `TwnNm` | `city` | `addressLocality` | locality |
| `street_address` | `StrtNm` and `BldgNb`, or an `AdrLine` in a hybrid address | `line` | `streetAddress` | street address |
| `description` | An `AdrLine` in a hybrid address | `line` | none | none |
| `location` | none | The `geolocation` extension | `geo` on the enclosing `Place` | The separate `GEO` property |

### Payments

`PstCd` holds [up to 16 characters](https://www.frbservices.org/wp-content/uploads/whats-in-an-iso-20022-message-sidebar.pdf), so the 15-character hyphenated code fits as written. `TwnNm`, `DstrctNm`, and `CtrySubDvsn` hold up to 35 characters each, `StrtNm` and an `AdrLine` up to 70, and `BldgNb` up to 16.

Swift is retiring unstructured addresses from cross-border payments in favour of structured and hybrid ones. In a hybrid address the town and the country are mandatory in their own fields, with up to two free-text lines beside them, according to [bank guidance](https://www.jpmorgan.com/insights/payments/cross-border-payments/iso-20022-migration). `locality` and `country` cover that minimum. The date, the field lengths, and the mandatory fields depend on the message version and the market, so check Swift's current notices and the usage guideline you send under.
