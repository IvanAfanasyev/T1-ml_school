from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
import re


@dataclass(frozen=True)
class KnownLocation:
    name: str
    latitude: float
    longitude: float
    aliases: tuple[str, ...]
    is_country: bool = False


KNOWN_LOCATIONS = (
    KnownLocation(
        name="Moscow",
        latitude=55.7558,
        longitude=37.6173,
        aliases=(
            "Moscow",
            "Moskva",
            "Москва",
            "Москве",
            "Москвы",
            "Московская область",
            "Московской области",
        ),
    ),
    KnownLocation(
        name="Saint-Petersburg",
        latitude=59.9311,
        longitude=30.3609,
        aliases=(
            "Saint-Petersburg",
            "Saint Petersburg",
            "St Petersburg",
            "SPB",
            "СПб",
            "Санкт-Петербург",
            "Санкт Петербург",
            "Санкт-Петербурге",
            "Петербург",
            "Петербурге",
            "Питер",
            "Питере",
            "Ленинградская область",
            "Ленинградской области",
        ),
    ),
    KnownLocation(
        name="Russia",
        latitude=61.5240,
        longitude=105.3188,
        aliases=(
            "Russia",
            "Россия",
            "России",
            "РФ",
            "Российская Федерация",
            "Российской Федерации",
        ),
        is_country=True,
    ),
    KnownLocation(
        name="Belgorod",
        latitude=50.5954,
        longitude=36.5872,
        aliases=(
            "Belgorod",
            "Белгород",
            "Белгороде",
            "Белгорода",
            "Белгородская область",
            "Белгородской области",
            "Белгородский район",
            "Белгородском районе",
        ),
    ),
    KnownLocation(
        name="Kursk",
        latitude=51.7304,
        longitude=36.1926,
        aliases=("Kursk", "Курск", "Курске", "Курская область", "Курской области"),
    ),
    KnownLocation(
        name="Voronezh",
        latitude=51.6608,
        longitude=39.2003,
        aliases=("Voronezh", "Воронеж", "Воронеже", "Воронежская область", "Воронежской области"),
    ),
    KnownLocation(
        name="Orel",
        latitude=52.9671,
        longitude=36.0695,
        aliases=("Orel", "Орел", "Орёл", "Орле", "Орловская область", "Орловской области"),
    ),
    KnownLocation(
        name="Tula",
        latitude=54.2048,
        longitude=37.6185,
        aliases=("Tula", "Тула", "Туле", "Тульская область", "Тульской области"),
    ),
    KnownLocation(
        name="Lipetsk",
        latitude=52.6088,
        longitude=39.5992,
        aliases=("Lipetsk", "Липецк", "Липецке", "Липецкая область", "Липецкой области"),
    ),
    KnownLocation(
        name="Bryansk",
        latitude=53.2521,
        longitude=34.3717,
        aliases=("Bryansk", "Брянск", "Брянске", "Брянская область", "Брянской области"),
    ),
    KnownLocation(
        name="Kaluga",
        latitude=54.5060,
        longitude=36.2516,
        aliases=("Kaluga", "Калуга", "Калуге", "Калужская область", "Калужской области"),
    ),
    KnownLocation(
        name="Ryazan",
        latitude=54.6292,
        longitude=39.7364,
        aliases=("Ryazan", "Рязань", "Рязани", "Рязанская область", "Рязанской области"),
    ),
    KnownLocation(
        name="Tver",
        latitude=56.8587,
        longitude=35.9176,
        aliases=("Tver", "Тверь", "Твери", "Тверская область", "Тверской области"),
    ),
    KnownLocation(
        name="Yaroslavl",
        latitude=57.6261,
        longitude=39.8845,
        aliases=("Yaroslavl", "Ярославль", "Ярославле", "Ярославская область", "Ярославской области"),
    ),
    KnownLocation(
        name="Nizhny Novgorod",
        latitude=56.2965,
        longitude=43.9361,
        aliases=(
            "Nizhny Novgorod",
            "Нижний Новгород",
            "Нижнем Новгороде",
            "Нижегородская область",
            "Нижегородской области",
        ),
    ),
    KnownLocation(
        name="Kazan",
        latitude=55.7879,
        longitude=49.1233,
        aliases=("Kazan", "Казань", "Казани", "Татарстан", "Республика Татарстан"),
    ),
    KnownLocation(
        name="Samara",
        latitude=53.1959,
        longitude=50.1002,
        aliases=("Samara", "Самара", "Самаре", "Самарская область", "Самарской области"),
    ),
    KnownLocation(
        name="Rostov-on-Don",
        latitude=47.2357,
        longitude=39.7015,
        aliases=(
            "Rostov-on-Don",
            "Rostov",
            "Ростов-на-Дону",
            "Ростове-на-Дону",
            "Ростовская область",
            "Ростовской области",
        ),
    ),
    KnownLocation(
        name="Krasnodar",
        latitude=45.0355,
        longitude=38.9753,
        aliases=("Krasnodar", "Краснодар", "Краснодаре", "Краснодарский край", "Краснодарском крае"),
    ),
    KnownLocation(
        name="Volgograd",
        latitude=48.7080,
        longitude=44.5133,
        aliases=("Volgograd", "Волгоград", "Волгограде", "Волгоградская область", "Волгоградской области"),
    ),
    KnownLocation(
        name="Ekaterinburg",
        latitude=56.8389,
        longitude=60.6057,
        aliases=("Ekaterinburg", "Yekaterinburg", "Екатеринбург", "Екатеринбурге", "Свердловская область"),
    ),
    KnownLocation(
        name="Perm",
        latitude=58.0105,
        longitude=56.2502,
        aliases=("Perm", "Пермь", "Перми", "Пермский край", "Пермском крае"),
    ),
    KnownLocation(
        name="Ufa",
        latitude=54.7388,
        longitude=55.9721,
        aliases=("Ufa", "Уфа", "Уфе", "Башкортостан", "Республика Башкортостан"),
    ),
    KnownLocation(
        name="Chelyabinsk",
        latitude=55.1644,
        longitude=61.4368,
        aliases=("Chelyabinsk", "Челябинск", "Челябинске", "Челябинская область"),
    ),
    KnownLocation(
        name="Novosibirsk",
        latitude=55.0084,
        longitude=82.9357,
        aliases=("Novosibirsk", "Новосибирск", "Новосибирске", "Новосибирская область"),
    ),
    KnownLocation(
        name="Omsk",
        latitude=54.9885,
        longitude=73.3242,
        aliases=("Omsk", "Омск", "Омске", "Омская область"),
    ),
    KnownLocation(
        name="Krasnoyarsk",
        latitude=56.0153,
        longitude=92.8932,
        aliases=("Krasnoyarsk", "Красноярск", "Красноярске", "Красноярский край"),
    ),
    KnownLocation(
        name="Irkutsk",
        latitude=52.2871,
        longitude=104.2807,
        aliases=("Irkutsk", "Иркутск", "Иркутске", "Иркутская область"),
    ),
    KnownLocation(
        name="Vladivostok",
        latitude=43.1155,
        longitude=131.8855,
        aliases=("Vladivostok", "Владивосток", "Владивостоке", "Приморский край"),
    ),
    KnownLocation(
        name="Khabarovsk",
        latitude=48.4802,
        longitude=135.0719,
        aliases=("Khabarovsk", "Хабаровск", "Хабаровске", "Хабаровский край"),
    ),
    KnownLocation(
        name="Kaliningrad",
        latitude=54.7104,
        longitude=20.4522,
        aliases=("Kaliningrad", "Калининград", "Калининграде", "Калининградская область"),
    ),
)


def normalize_location_key(value: str | None) -> str:
    if value is None:
        return ""

    text = value.strip().lower().replace("ё", "е")
    text = re.sub(r"[^a-zа-я0-9]+", " ", text)
    return " ".join(text.split())


_ALIASES_BY_KEY = {
    normalize_location_key(alias): location.name
    for location in KNOWN_LOCATIONS
    for alias in (location.name, *location.aliases)
}

_LOCATIONS_BY_NAME = {
    location.name: location
    for location in KNOWN_LOCATIONS
}


def canonicalize_region(region: str | None) -> str | None:
    if region is None:
        return None

    key = normalize_location_key(region)
    if not key:
        return None

    for candidate_key in _region_alias_keys(key):
        if candidate_key in _ALIASES_BY_KEY:
            return _ALIASES_BY_KEY[candidate_key]

    return region.strip()


def _region_alias_keys(key: str) -> list[str]:
    keys = [key]

    for prefix in ("в ", "во ", "на "):
        if key.startswith(prefix):
            keys.append(key.removeprefix(prefix))

    return keys


def extract_region_from_text(text: str) -> str | None:
    query_key = normalize_location_key(text)
    if not query_key:
        return None

    padded_query = f" {query_key} "

    aliases = sorted(
        _ALIASES_BY_KEY.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )

    for alias_key, region_name in aliases:
        if f" {alias_key} " in padded_query:
            return region_name

    return None


def match_available_region(
    requested_region: str | None,
    available_regions: list[str],
) -> str | None:
    requested_canonical = canonicalize_region(requested_region)
    requested_key = normalize_location_key(requested_canonical)

    if not requested_key:
        return None

    matched_regions = []

    for available_region in available_regions:
        available_key = normalize_location_key(canonicalize_region(available_region))
        if available_key == requested_key:
            matched_regions.append(available_region)

    if not matched_regions:
        return None

    for available_region in matched_regions:
        if available_region == requested_canonical:
            return available_region

    return matched_regions[0]


def resolve_nearby_available_regions(
    requested_region: str | None,
    available_regions: list[str],
    limit: int = 3,
) -> list[str]:
    requested_canonical = canonicalize_region(requested_region)

    if requested_canonical is None:
        return []

    exact_region = match_available_region(requested_canonical, available_regions)
    exact_key = normalize_location_key(canonicalize_region(exact_region))
    requested_location = _LOCATIONS_BY_NAME.get(requested_canonical)

    if requested_location is None:
        return [exact_region] if exact_region else _country_fallback(available_regions)

    if requested_location.is_country:
        return [exact_region] if exact_region else _country_fallback(available_regions)

    city_candidates_by_key: dict[str, tuple[float, str]] = {}
    country_candidates_by_key: dict[str, str] = {}

    for available_region in available_regions:
        available_canonical = canonicalize_region(available_region)
        available_location = _LOCATIONS_BY_NAME.get(available_canonical or "")
        available_key = normalize_location_key(available_canonical)

        if available_location is None:
            continue

        if exact_key and available_key == exact_key:
            continue

        if available_location.is_country:
            country_candidates_by_key.setdefault(
                available_key,
                _preferred_available_region(
                    canonical_name=available_location.name,
                    available_region=available_region,
                ),
            )
            continue

        distance = _distance_km(requested_location, available_location)
        preferred_region = _preferred_available_region(
            canonical_name=available_location.name,
            available_region=available_region,
        )

        current_candidate = city_candidates_by_key.get(available_key)
        if current_candidate is None or distance < current_candidate[0]:
            city_candidates_by_key[available_key] = (distance, preferred_region)

    city_candidates = sorted(
        city_candidates_by_key.values(),
        key=lambda item: item[0],
    )

    nearby_regions = [region for _, region in city_candidates]
    nearby_regions.extend(country_candidates_by_key.values())

    if exact_region:
        return [exact_region, *nearby_regions][:limit]

    return nearby_regions[:limit]


def _preferred_available_region(
    canonical_name: str,
    available_region: str,
) -> str:
    if normalize_location_key(canonical_name) == normalize_location_key(available_region):
        return canonical_name

    return available_region


def _country_fallback(available_regions: list[str]) -> list[str]:
    for available_region in available_regions:
        if canonicalize_region(available_region) == "Russia":
            return [available_region]

    return []


def _distance_km(first: KnownLocation, second: KnownLocation) -> float:
    radius_km = 6371.0

    lat1 = radians(first.latitude)
    lon1 = radians(first.longitude)
    lat2 = radians(second.latitude)
    lon2 = radians(second.longitude)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    haversine = (
        sin(dlat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    )

    return 2 * radius_km * asin(sqrt(haversine))
