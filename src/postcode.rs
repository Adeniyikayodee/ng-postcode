use std::fmt;
use std::ops::Range;
use std::str::FromStr;

use Segment::{Area, District, Lga, State, Unit};

const LEN: usize = 11;

/// A well-formed postcode, held in its compact upper-case form.
///
/// Well formed is not the same as assigned: only the NIPOST API knows whether
/// a code belongs to a real building.
#[derive(Clone, Copy, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub struct Postcode([u8; LEN]);

/// The five segments of a postcode, `AA-99-H77-BB-55`, from widest to narrowest.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash, PartialOrd, Ord)]
pub enum Segment {
    /// Two letters.
    State,
    /// Two digits, 01 to 99.
    Lga,
    /// Three letters or digits.
    District,
    /// Two letters.
    Area,
    /// Two digits, 01 to 99.
    Unit,
}

/// Why a string is not a well-formed postcode.
#[derive(Clone, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub enum ParseError {
    /// The input did not hold exactly 11 letters and digits.
    Length { found: usize },
    /// The input held something other than letters, digits, spaces and hyphens.
    InvalidCharacter { ch: char, index: usize },
    /// A segment has the wrong shape, such as digits in the state.
    Segment(Segment),
}

/// The result of [`Postcode::parse_lenient`].
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[non_exhaustive]
pub struct Corrected {
    pub postcode: Postcode,
    /// How many characters were swapped for their look-alike.
    pub corrections: usize,
}

impl Postcode {
    /// Parses a hyphenated, spaced or compact code in either case.
    pub fn parse(input: &str) -> Result<Self, ParseError> {
        collect(input).and_then(validate).map(Self)
    }

    /// Parses like [`parse`](Self::parse) after swapping look-alike characters
    /// that cannot occur where they stand: `0 1 5 8` for `O I S B` where a
    /// letter is required, and the reverse (plus `L` for `1`) where a digit is.
    ///
    /// The result is well formed but may not be the code the user meant, so
    /// confirm it with them when `corrections` is not zero.
    pub fn parse_lenient(input: &str) -> Result<Corrected, ParseError> {
        let raw = collect(input)?;
        let fixed: [u8; LEN] =
            std::array::from_fn(|i| Segment::at(i).map_or(raw[i], |s| s.unconfuse(raw[i])));
        let corrections = raw.iter().zip(&fixed).filter(|(a, b)| a != b).count();
        validate(fixed).map(|bytes| Corrected {
            postcode: Self(bytes),
            corrections,
        })
    }

    /// Builds a code from its segments, zero-filling the LGA and unit so that
    /// `"1"` becomes `"01"`.
    pub fn from_segments(
        state: &str,
        lga: &str,
        district: &str,
        area: &str,
        unit: &str,
    ) -> Result<Self, ParseError> {
        let parts = [
            State.padded(state)?,
            Lga.padded(lga)?,
            District.padded(district)?,
            Area.padded(area)?,
            Unit.padded(unit)?,
        ];
        Self::parse(&parts.concat())
    }

    /// The compact form, `EK01A03FK01`. Store and compare this one.
    pub fn as_str(&self) -> &str {
        std::str::from_utf8(&self.0).expect("postcode bytes are ASCII")
    }

    /// The spaced form shown to people, `EK 01 A03 FK 01`.
    pub fn to_spaced(&self) -> String {
        self.joined(Unit, " ")
    }

    /// The hyphenated code down to and including `through`, so
    /// `prefix(Segment::Area)` is `EK-01-A03-FK`.
    pub fn prefix(&self, through: Segment) -> String {
        self.joined(through, "-")
    }

    pub fn segment(&self, segment: Segment) -> &str {
        &self.as_str()[segment.range()]
    }

    pub fn state(&self) -> &str {
        self.segment(State)
    }

    pub fn lga(&self) -> &str {
        self.segment(Lga)
    }

    pub fn district(&self) -> &str {
        self.segment(District)
    }

    pub fn area(&self) -> &str {
        self.segment(Area)
    }

    pub fn unit(&self) -> &str {
        self.segment(Unit)
    }

    fn joined(&self, through: Segment, separator: &str) -> String {
        Segment::ALL
            .into_iter()
            .take_while(|&s| s <= through)
            .map(|s| self.segment(s))
            .collect::<Vec<_>>()
            .join(separator)
    }
}

/// Whether `input` is a well-formed postcode.
pub fn is_valid(input: &str) -> bool {
    Postcode::parse(input).is_ok()
}

impl Segment {
    const ALL: [Self; 5] = [State, Lga, District, Area, Unit];

    const fn range(self) -> Range<usize> {
        match self {
            State => 0..2,
            Lga => 2..4,
            District => 4..7,
            Area => 7..9,
            Unit => 9..11,
        }
    }

    fn at(index: usize) -> Option<Self> {
        Self::ALL.into_iter().find(|s| s.range().contains(&index))
    }

    fn accepts(self, bytes: &[u8]) -> bool {
        match self {
            State | Area => bytes.iter().all(u8::is_ascii_uppercase),
            // 00 is never issued.
            Lga | Unit => bytes.iter().all(u8::is_ascii_digit) && bytes != b"00",
            District => bytes.iter().all(u8::is_ascii_alphanumeric),
        }
    }

    fn unconfuse(self, byte: u8) -> u8 {
        match (self, byte) {
            (State | Area, b'0') => b'O',
            (State | Area, b'1') => b'I',
            (State | Area, b'5') => b'S',
            (State | Area, b'8') => b'B',
            (Lga | Unit, b'O') => b'0',
            (Lga | Unit, b'I' | b'L') => b'1',
            (Lga | Unit, b'S') => b'5',
            (Lga | Unit, b'B') => b'8',
            _ => byte,
        }
    }

    fn padded(self, value: &str) -> Result<String, ParseError> {
        let (value, width) = (value.trim(), self.range().len());
        let shortest = if matches!(self, Lga | Unit) { 1 } else { width };
        let fits = (shortest..=width).contains(&value.len())
            && value.bytes().all(|b| b.is_ascii_alphanumeric());
        if fits {
            Ok(format!("{value:0>width$}"))
        } else {
            Err(ParseError::Segment(self))
        }
    }
}

fn collect(input: &str) -> Result<[u8; LEN], ParseError> {
    // Every character is checked, but only a postcode's worth is held: no allocation.
    let mut bytes = [0; LEN];
    let mut found = 0;
    for (index, ch) in input.char_indices() {
        if ch == ' ' || ch == '-' {
            continue;
        }
        if !ch.is_ascii_alphanumeric() {
            return Err(ParseError::InvalidCharacter { ch, index });
        }
        if let Some(slot) = bytes.get_mut(found) {
            *slot = ch.to_ascii_uppercase() as u8;
        }
        found += 1;
    }
    match found {
        LEN => Ok(bytes),
        _ => Err(ParseError::Length { found }),
    }
}

fn validate(bytes: [u8; LEN]) -> Result<[u8; LEN], ParseError> {
    match Segment::ALL
        .into_iter()
        .find(|s| !s.accepts(&bytes[s.range()]))
    {
        Some(segment) => Err(ParseError::Segment(segment)),
        None => Ok(bytes),
    }
}

impl FromStr for Postcode {
    type Err = ParseError;

    fn from_str(s: &str) -> Result<Self, Self::Err> {
        Self::parse(s)
    }
}

/// The canonical hyphenated form, `EK-01-A03-FK-01`.
impl fmt::Display for Postcode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.prefix(Unit))
    }
}

impl fmt::Debug for Postcode {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "Postcode({self})")
    }
}

impl fmt::Display for Segment {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            State => "state",
            Lga => "lga",
            District => "district",
            Area => "area",
            Unit => "unit",
        })
    }
}

impl fmt::Display for ParseError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Length { found } => write!(f, "expected {LEN} letters and digits, found {found}"),
            Self::InvalidCharacter { ch, index } => {
                write!(f, "invalid character '{ch}' at index {index}")
            }
            Self::Segment(segment) => write!(f, "invalid {segment} segment"),
        }
    }
}

impl std::error::Error for ParseError {}

#[cfg(feature = "serde")]
impl serde::Serialize for Postcode {
    fn serialize<S: serde::Serializer>(&self, serializer: S) -> Result<S::Ok, S::Error> {
        serializer.collect_str(self)
    }
}

#[cfg(feature = "serde")]
impl<'de> serde::Deserialize<'de> for Postcode {
    fn deserialize<D: serde::Deserializer<'de>>(deserializer: D) -> Result<Self, D::Error> {
        let text = <std::borrow::Cow<'de, str>>::deserialize(deserializer)?;
        text.parse().map_err(serde::de::Error::custom)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // The test postcodes published in the NIPOST API docs.
    const PUBLISHED: &str = "\
        EK-01-A03-FK-01 AK-11-I61-ZF-12 AK-11-H40-WD-11 BA-02-M67-BL-69 BA-02-E99-NE-30 \
        EB-13-G95-FR-90 EB-13-I97-AB-30 EN-05-V19-CD-22 EN-05-V19-FT-20 FC-03-B06-AG-12 \
        FC-02-B19-RT-30 JI-24-O18-JP-23 JI-24-N11-VM-58 KN-31-F82-WJ-80 KN-31-D78-IQ-38 \
        LA-11-W06-TC-10 LA-11-U34-ZR-63 NI-09-J67-QC-65 NI-09-A75-DA-10 OG-14-T18-BN-16 \
        OG-14-M82-QA-09";

    fn parsed(code: &str) -> Postcode {
        Postcode::parse(code).unwrap()
    }

    #[test]
    fn published_codes_round_trip_unchanged() {
        assert_eq!(PUBLISHED.split_whitespace().count(), 21);
        for code in PUBLISHED.split_whitespace() {
            assert_eq!(parsed(code).to_string(), code);
            let lenient = Postcode::parse_lenient(code).unwrap();
            assert_eq!((lenient.postcode, lenient.corrections), (parsed(code), 0));
        }
    }

    #[test]
    fn accepts_every_input_style() {
        let code = parsed("EK-01-A03-FK-01");
        assert_eq!(parsed("EK 01 A03 FK 01"), code);
        assert_eq!(parsed("ek01a03fk01"), code);
    }

    #[test]
    fn formats() {
        let code = parsed("ek01a03fk01");
        assert_eq!(code.as_str(), "EK01A03FK01");
        assert_eq!(code.to_string(), "EK-01-A03-FK-01");
        assert_eq!(code.to_spaced(), "EK 01 A03 FK 01");
        assert_eq!(format!("{code:?}"), "Postcode(EK-01-A03-FK-01)");
    }

    #[test]
    fn exposes_segments_and_prefixes() {
        let code = parsed("LA-11-W06-TC-10");
        let segments = [
            code.state(),
            code.lga(),
            code.district(),
            code.area(),
            code.unit(),
        ];
        assert_eq!(segments, ["LA", "11", "W06", "TC", "10"]);
        assert_eq!(code.prefix(Segment::State), "LA");
        assert_eq!(code.prefix(Segment::District), "LA-11-W06");
        assert_eq!(code.prefix(Segment::Area), "LA-11-W06-TC");
    }

    #[test]
    fn from_segments_zero_fills_numbers_only() {
        let built = Postcode::from_segments("ek", " 1", "a03", "fk", "1");
        assert_eq!(built, Ok(parsed("EK-01-A03-FK-01")));

        let rejects = |segments: [&str; 5], segment| {
            let [state, lga, district, area, unit] = segments;
            let built = Postcode::from_segments(state, lga, district, area, unit);
            assert_eq!(built, Err(ParseError::Segment(segment)));
        };
        rejects(["E", "1", "A03", "FK", "1"], Segment::State);
        rejects(["EK", "001", "A03", "FK", "1"], Segment::Lga);
        rejects(["EK", "1", "A3", "FK", "1"], Segment::District);
        rejects(["EK", "1", "A03", "F-", "1"], Segment::Area);
        rejects(["EK", "1", "A03", "FK", ""], Segment::Unit);
    }

    #[test]
    fn rejects_malformed_input() {
        let rejects = |input, error| assert_eq!(Postcode::parse(input), Err(error));
        rejects("", ParseError::Length { found: 0 });
        rejects("EK-01-A03-FK", ParseError::Length { found: 9 });
        rejects("EK-01-A03-FK-011", ParseError::Length { found: 12 });
        rejects(
            "EK_01-A03-FK-01",
            ParseError::InvalidCharacter { ch: '_', index: 2 },
        );
        rejects(
            "ÉK-01-A03-FK-01",
            ParseError::InvalidCharacter { ch: 'É', index: 0 },
        );
        rejects("E1-01-A03-FK-01", ParseError::Segment(Segment::State));
        rejects("EK-0A-A03-FK-01", ParseError::Segment(Segment::Lga));
        rejects("EK-00-A03-FK-01", ParseError::Segment(Segment::Lga));
        rejects("EK-01-A03-F7-01", ParseError::Segment(Segment::Area));
        rejects("EK-01-A03-FK-00", ParseError::Segment(Segment::Unit));
    }

    #[test]
    fn lenient_swaps_lookalikes_by_position() {
        let fixes = |input, code, corrections| {
            let expected = Corrected {
                postcode: parsed(code),
                corrections,
            };
            assert_eq!(Postcode::parse_lenient(input), Ok(expected));
        };
        fixes("EK-O1-A03-FK-0I", "EK-01-A03-FK-01", 2);
        fixes("0G-14-T18-8N-l6", "OG-14-T18-BN-16", 3);
        // The district allows letters and digits, so it is never rewritten.
        fixes("JI-24-O18-JP-23", "JI-24-O18-JP-23", 0);
    }

    #[test]
    fn lenient_rejects_what_it_cannot_fix() {
        let rejects = |input| {
            let error = ParseError::Segment(Segment::Lga);
            assert_eq!(Postcode::parse_lenient(input), Err(error));
        };
        rejects("EK-0X-A03-FK-01");
        rejects("EK-OO-A03-FK-01");
    }

    #[test]
    fn orders_by_hierarchy() {
        let sorted = ["EK-01-A03-FK-01", "EK-01-A03-FK-02", "LA-11-W06-TC-10"].map(parsed);
        let mut shuffled = [sorted[2], sorted[0], sorted[1]];
        shuffled.sort();
        assert_eq!(shuffled, sorted);
    }

    #[test]
    fn is_valid_agrees_with_parse() {
        assert!(is_valid("ek 01 a03 fk 01"));
        assert!(!is_valid("EK-01-A03"));
    }

    #[cfg(feature = "serde")]
    #[test]
    fn serde_round_trips_through_the_canonical_form() {
        let code: Postcode = serde_json::from_str("\"ek01a03fk01\"").unwrap();
        assert_eq!(serde_json::to_string(&code).unwrap(), "\"EK-01-A03-FK-01\"");
        assert!(serde_json::from_str::<Postcode>("\"EK-01\"").is_err());
    }
}
