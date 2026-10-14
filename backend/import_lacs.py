
from sqlalchemy import text

from app.core.database import SessionLocal


# District names from the source list mapped to existing database IDs.
DISTRICT_IDS = {
    "TRIVANDRUM": 1,
    "KOLLAM": 2,
    "PATHANAMTHITTA": 3,
    "ALAPPUZHA": 4,
    "KOTTAYAM": 5,
    "IDUKKI": 6,
    "ERANAKULAM": 7,
    "TRICHUR": 8,
    "PALAKKAD": 9,
    "MALAPPURAM": 10,
    "KOZHIKODE": 11,
    "WYNAD": 12,
    "KANNUR": 13,
    "KASARAGOD": 14,
}

# Source format:
# (code, name, district from source, latitude, longitude)
LACS = [
    ("001", "MANJESHWAR", "KASARAGOD", 12.7242, 74.8876),
    ("002", "KASARAGOD", "KASARAGOD", 12.5076, 74.9882),
    ("003", "UDMA", "KASARAGOD", 12.444, 75.024),
    ("004", "KANHANGAD", "KASARAGOD", 12.3000, 75.0900),
    ("005", "TRIKARIPUR", "KASARAGOD", 12.14389, 75.17889),
    ("006", "PAYYANNUR", "KANNUR", 12.1, 75.2),
    ("007", "KALLIASSERI", "KANNUR", 11.9712, 75.3616),
    ("008", "TALIPARAMBA", "KANNUR", 12.0383, 75.3675),
    ("009", "IRIKKUR", "KANNUR", 11.9869, 75.5539),
    ("010", "AZHIKODE", "KANNUR", 11.9186, 75.3358),
    ("011", "KANNUR", "KANNUR", 11.8745, 75.3704),
    ("012", "DHARMADAM", "KANNUR", 11.7754, 75.4646),
    ("013", "THALASSERY", "KANNUR", 11.7481, 75.4929),
    ("014", "KUTHUPARAMBA", "KANNUR", 11.8300, 75.5800),
    ("015", "MATTANNUR", "KANNUR", 11.931, 75.572),
    ("016", "PERAVOOR", "KANNUR", 11.8962, 75.7342),
    ("017", "MANANTHAVADY (ST)", "WYNAD", 11.8014, 76.0044),
    ("018", "SULTHANBATHERY (ST)", "WYNAD", 11.67, 76.28),
    ("019", "KALPETTA", "WYNAD", 11.6106, 76.0822),
    ("020", "VADAKARA", "KOZHIKODE", 11.6085, 75.5917),
    ("021", "KUTTIADI", "KOZHIKODE", 11.65487, 75.75438),
    ("022", "NADAPURAM", "KOZHIKODE", 11.7109, 75.6562),
    ("023", "QUILANDY", "KOZHIKODE", 11.43, 75.70),
    ("024", "PERAMBRA", "KOZHIKODE", 11.5575, 75.7605),
    ("025", "BALUSSERI (SC)", "KOZHIKODE", 11.45, 75.83),
    ("026", "ELATHUR", "KOZHIKODE", 11.34361, 75.73854),
    ("027", "KOZHIKODE NORTH", "KOZHIKODE", 11.258753, 75.780411),
    ("028", "KOZHIKODE SOUTH", "KOZHIKODE", 11.2588, 75.7804),
    ("029", "BEYPORE", "KOZHIKODE", 11.1715, 75.8061),
    ("030", "KUNNAMANGALAM", "KOZHIKODE", 11.3047, 75.8778),
    ("031", "KODUVALLY", "KOZHIKODE", 11.3597, 75.9129),
    ("032", "THIRUVAMBADY", "KOZHIKODE", 11.3611, 76.0095),
    ("033", "KONDOTTY", "MALAPPURAM", 11.1423, 75.9657),
    ("034", "ERANAD", "MALAPPURAM", 11.1342, 76.0960),
    ("035", "NILAMBUR", "MALAPPURAM", 11.2785, 76.2398),
    ("036", "WANDOOR (SC)", "MALAPPURAM", 11.1950, 76.2360),
    ("037", "MANJERI", "MALAPPURAM", 11.1202, 76.1167),
    ("038", "PERINTHALMANNA", "MALAPPURAM", 10.9755, 76.2305),
    ("039", "MANKADA", "MALAPPURAM", 11.0189, 76.0734),
    ("040", "MALAPPURAM", "MALAPPURAM", 11.0720, 76.0740),
    ("041", "VENGARA", "MALAPPURAM", 11.0511, 75.9829),
    ("042", "VALLIKKUNNU", "MALAPPURAM", 11.0927, 75.8447),
    ("043", "TIRURANGADI", "MALAPPURAM", 11.0422, 75.9279),
    ("044", "TANUR", "MALAPPURAM", 10.9820, 75.8754),
    ("045", "TIRUR", "MALAPPURAM", 10.9146, 75.9221),
    ("046", "KOTTAKKAL", "MALAPPURAM", 11.0022, 75.9988),
    ("047", "THAVANUR", "MALAPPURAM", 10.8514, 75.9986),
    ("048", "PONNANI", "MALAPPURAM", 10.7677, 75.9259),
    ("049", "THRITHALA", "PALAKKAD", 10.8030, 76.1290),
    ("050", "PATTAMBI", "PALAKKAD", 10.8068, 76.1965),
    ("051", "SHORNUR", "PALAKKAD", 10.7626, 76.2694),
    ("052", "OTTAPALAM", "PALAKKAD", 10.7700, 76.3737),
    ("053", "KONGAD (SC)", "PALAKKAD", 10.8540, 76.5216),
    ("054", "MANNARKAD", "PALAKKAD", 10.9800, 76.4700),
    ("055", "MALAMPUZHA", "PALAKKAD", 10.8320, 76.6531),
    ("056", "PALAKKAD", "PALAKKAD", 10.7847, 76.6548),
    ("057", "TARUR (SC)", "PALAKKAD", 10.6558, 76.4694),
    ("058", "CHITTUR", "PALAKKAD", 10.5763, 76.6953),
    ("059", "NENMARA", "PALAKKAD", 10.5934, 76.6006),
    ("060", "ALATHUR", "PALAKKAD", 10.6470, 76.5450),
    ("061", "CHELAKKARA (SC)", "TRICHUR", 10.7041, 76.3206),
    ("062", "KUNNAMKULAM", "TRICHUR", 10.6484, 76.0694),
    ("063", "GURUVAYOOR", "TRICHUR", 10.5947, 76.0397),
    ("064", "MANALUR", "TRICHUR", 10.4980, 76.1002),
    ("065", "WADAKKANCHERY", "TRICHUR", 10.6617, 76.2455),
    ("066", "OLLUR", "TRICHUR", 10.4785, 76.2370),
    ("067", "THRISSUR", "TRICHUR", 10.5231, 76.2147),
    ("068", "NATTIKA (SC)", "TRICHUR", 10.4072, 76.1150),
    ("069", "KAIPAMANGALAM", "TRICHUR", 10.3350, 76.1390),
    ("070", "IRINJALAKKUDA", "TRICHUR", 10.3454, 76.2094),
    ("071", "PUTHUKKAD", "TRICHUR", 10.4212, 76.2703),
    ("072", "CHALAKKUDY", "TRICHUR", 10.3070, 76.3320),
    ("073", "KODUNGALLUR", "TRICHUR", 10.2167, 76.2167),
    ("074", "PERUMBAVOOR", "ERANAKULAM", 10.10695, 76.47366),
    ("075", "ANGAMALY", "ERANAKULAM", 10.196, 76.386),
    ("076", "ALUVA", "ERANAKULAM", 10.1078, 76.3507),
    ("077", "KALAMASSERY", "ERANAKULAM", 10.0614, 76.32631),
    ("078", "PARAVUR", "ERANAKULAM", 10.140487, 76.230530),
    ("079", "VYPEN", "ERANAKULAM", 9.973429, 76.244140),
    ("080", "KOCHI", "ERANAKULAM", 9.9399, 76.2602),
    ("081", "THRIPUNITHURA", "ERANAKULAM", 9.9496, 76.3445),
    ("082", "ERANAKULAM", "ERANAKULAM", 9.9816, 76.2999),
    ("083", "THRIKKAKARA", "ERANAKULAM", 10.032715, 76.331889),
    ("084", "KUNNATHUNAD (SC)", "ERANAKULAM", 10.1083, 76.4417),
    ("085", "PIRAVOM", "ERANAKULAM", 9.8734, 76.4923),
    ("086", "MUVATTUPUZHA", "ERANAKULAM", 9.99051, 76.57891),
    ("087", "KOTHAMANGALAM", "ERANAKULAM", 10.06019, 76.63508),
    ("088", "DEVIKULAM (SC)", "IDUKKI", 10.062640, 77.103990),
    ("089", "UDUMBANCHOLA", "IDUKKI", 9.899356, 77.18148),
    ("090", "THODUPUZHA", "IDUKKI", 9.8939, 76.7222),
    ("091", "IDUKKI", "IDUKKI", 9.85, 76.9667),
    ("092", "PEERUMADE", "IDUKKI", 9.577778, 77.020833),
    ("093", "PALA", "KOTTAYAM", 9.708380, 76.684914),
    ("094", "KADATHURUTHY", "KOTTAYAM", 9.7709041, 76.4800996),
    ("095", "VAIKOM (SC)", "KOTTAYAM", 9.7471, 76.3952),
    ("096", "ETTUMANOOR", "KOTTAYAM", 9.6704, 76.5609),
    ("097", "KOTTAYAM", "KOTTAYAM", 9.58692, 76.52132),
    ("098", "PUTHUPPALLY", "KOTTAYAM", 9.559433, 76.572217),
    ("099", "CHANGANASSERY", "KOTTAYAM", 9.4458875, 76.5409655),
    ("100", "KANJIRAPPALLY", "KOTTAYAM", 9.557270, 76.789436),
    ("101", "POONJAR", "KOTTAYAM", 9.6744, 76.8087),
    ("102", "AROOR", "ALAPPUZHA", 9.8694, 76.305),
    ("103", "CHERTHALA", "ALAPPUZHA", 9.68444, 76.33558),
    ("104", "ALAPPUZHA", "ALAPPUZHA", 9.4981, 76.3388),
    ("105", "AMBALAPUZHA", "ALAPPUZHA", 9.377914, 76.357391),
    ("106", "KUTTANAD", "ALAPPUZHA", 9.15360, 76.47300),
    ("107", "HARIPAD", "ALAPPUZHA", 9.3000, 76.4667),
    ("108", "KAYUMKULAM", "ALAPPUZHA", 9.182, 76.501),
    ("109", "MAVELIKARA (SC)", "ALAPPUZHA", 9.25929, 76.55642),
    ("110", "CHENGANNUR", "ALAPPUZHA", 9.31575, 76.6151),
    ("111", "THIRUVALLA", "PATHANAMTHITTA", 9.3835, 76.5741),
    ("112", "RANNI", "PATHANAMTHITTA", 9.3667, 76.81),
    ("113", "ARANMULA", "PATHANAMTHITTA", 9.3333, 76.6833),
    ("114", "KONNI", "PATHANAMTHITTA", 9.2246, 76.8476),
    ("115", "ADOOR (SC)", "PATHANAMTHITTA", 9.156651, 76.730766),
    ("116", "KARUNAGAPPALLY", "KOLLAM", 9.0544, 76.5353),
    ("117", "CHAVARA", "KOLLAM", 8.97578, 76.53513),
    ("118", "KUNNATHUR (SC)", "KOLLAM", 9.0438, 76.6715),
    ("119", "KOTTARAKKARA", "KOLLAM", 9.004, 76.774),
    ("120", "PATHANAPURAM", "KOLLAM", 9.09048, 76.89394),
    ("121", "PUNALOOR", "KOLLAM", 9.01956, 76.9226),
    ("122", "CHADAYAMANGALAM", "KOLLAM", 8.873124, 76.869394),
    ("123", "KUNDARA", "KOLLAM", 8.9601841, 76.6788091),
    ("124", "KOLLAM", "KOLLAM", 8.88113, 76.58469),
    ("125", "ERAVIPURAM", "KOLLAM", 8.86667, 76.61667),
    ("126", "CHATHANNOOR", "KOLLAM", 8.85667, 76.71806),
    ("127", "VARKALA", "TRIVANDRUM", 8.7333, 76.7167),
    ("128", "ATTINGAL (SC)", "TRIVANDRUM", 8.69609, 76.8151),
    ("129", "CHIRAYANKEEZHU (SC)", "TRIVANDRUM", 8.65587, 76.783174),
    ("130", "NEDUMANGAD", "TRIVANDRUM", 8.6033, 77.0028),
    ("131", "VAMANAPURAM", "TRIVANDRUM", 8.7200343, 76.8980371),
    ("132", "KAZHAKKOOTTAM", "TRIVANDRUM", 8.56556, 76.87472),
    ("133", "VATTIYOORKAVU", "TRIVANDRUM", 8.52385, 76.98707),
    ("134", "THIRUVANANTHAPURAM", "TRIVANDRUM", 8.5241, 76.9366),
    ("135", "NEMOM", "TRIVANDRUM", 8.457895, 76.999394),
    ("136", "ARUVIKKARA", "TRIVANDRUM", 8.567, 77.017),
    ("137", "PARASALA", "TRIVANDRUM", 8.3431, 77.1526),
    ("138", "KATTAKADA", "TRIVANDRUM", 8.5033, 77.0852),
    ("139", "KOVALAM", "TRIVANDRUM", 8.4004, 76.9787),
    ("140", "NEYYATTINKARA", "TRIVANDRUM", 8.3985, 77.0859),
]


def import_lacs():
    if len(LACS) != 140:
        raise ValueError(f"Expected 140 LAC records, found {len(LACS)}")

    codes = [lac[0] for lac in LACS]
    if len(codes) != len(set(codes)):
        raise ValueError("Duplicate LAC codes found in import data")

    db = SessionLocal()

    try:
        # Verify that every expected district exists before importing.
        for source_district, district_id in DISTRICT_IDS.items():
            district = db.execute(
                text(
                    """
                    SELECT id
                    FROM locations
                    WHERE id = :district_id
                      AND location_type = 'DISTRICT'
                    """
                ),
                {"district_id": district_id},
            ).first()

            if district is None:
                raise ValueError(
                    f"Expected district ID {district_id} "
                    f"for {source_district} was not found."
                )

        inserted = 0
        updated = 0

        for code, name, source_district, latitude, longitude in LACS:
            district_id = DISTRICT_IDS[source_district]

            existing = db.execute(
                text(
                    """
                    SELECT id
                    FROM locations
                    WHERE location_type = 'LAC'
                      AND administrative_code = :code
                    """
                ),
                {"code": code},
            ).first()

            values = {
                "name": name,
                "location_type": "LAC",
                "parent_id": district_id,
                "code": code,
                "latitude": latitude,
                "longitude": longitude,
            }

            if existing:
                db.execute(
                    text(
                        """
                        UPDATE locations
                        SET name = :name,
                            parent_id = :parent_id,
                            latitude = :latitude,
                            longitude = :longitude
                        WHERE id = :id
                        """
                    ),
                    {**values, "id": existing.id},
                )
                updated += 1
            else:
                db.execute(
                    text(
                        """
                        INSERT INTO locations
                            (name, location_type, parent_id,
                             administrative_code, latitude, longitude)
                        VALUES
                            (:name, :location_type, :parent_id,
                             :code, :latitude, :longitude)
                        """
                    ),
                    values,
                )
                inserted += 1

        db.commit()

        total = db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM locations
                WHERE location_type = 'LAC'
                """
            )
        ).scalar_one()

        print(f"New LAC records inserted: {inserted}")
        print(f"Existing LAC records updated: {updated}")
        print(f"Total LAC records in database: {total}")

        if total != 140:
            raise ValueError(
                f"Expected 140 LAC records after import, found {total}"
            )

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import_lacs()
