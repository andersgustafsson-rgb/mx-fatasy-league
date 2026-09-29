"""SEO tippa-page content helpers (no Flask routes)."""
from __future__ import annotations

import json
import os


def _llms_txt_body(base: str) -> str:
    """Curated site map for AI agents / coding tools that fetch /llms.txt."""
    return (
        "# MX Fantasy League\n"
        "\n"
        "> Gratis fantasy motocross-spel i Sverige. Tippa SX, MX, SMX, WSX, MXGP och MXoN "
        "— ligor, poäng och leaderboard utan betting.\n"
        "\n"
        "Officiell webbplats: https://mx-fantasy.se\n"
        "\n"
        "## Viktiga sidor\n"
        f"- [Startsida]({base}/): tippa race, topplista och spelöversikt\n"
        f"- [Om spelet]({base}/om): vad MX Fantasy League är, hur tippning fungerar, FAQ\n"
        f"- [Tippa supercross]({base}/tippa-supercross): tippa AMA Supercross / SX gratis\n"
        f"- [Tippa motocross]({base}/tippa-motocross): tippa Pro Motocross / MX gratis\n"
        f"- [Tippa SMX]({base}/tippa-smx): tippa SuperMotocross Playoffs / Final gratis\n"
        f"- [Tippa WSX]({base}/tippa-wsx): tippa World Supercross (SX1/SX2) gratis\n"
        f"- [Tippa MXGP]({base}/tippa-mxgp): tippa FIM MXGP / MX2-världsmästerskapet gratis\n"
        f"- [Tippa MXoN]({base}/tippa-mxon): tippa Motocross of Nations (länder) gratis\n"
        f"- [Spelmanual]({base}/manual): regler, poängsystem, holeshot och wildcard\n"
        f"- [Starta / bjud in]({base}/start): skapa konto och gå med\n"
        f"- [Registrera]({base}/register): gratis konto\n"
        "\n"
        "## Kort fakta\n"
        "- Namn: MX Fantasy League (även MX Fantasy)\n"
        "- Språk: svenska\n"
        "- Kostnad: gratis, ingen betting\n"
        "- Serier: SX, MX, SMX, WSX, MXGP, MXON\n"
        f"- Sitemap: {base}/sitemap.xml\n"
        f"- Facebook: {os.getenv('FACEBOOK_PAGE_URL') or 'https://www.facebook.com/profile.php?id=61586769893903'}\n"
    )
def _tippa_serie_faq_json(faq_items: list[dict]) -> str:

    entity = [
        {
            "@type": "Question",
            "name": item["q"],
            "acceptedAnswer": {"@type": "Answer", "text": item["a_plain"]},
        }
        for item in faq_items
    ]
    return json.dumps(
        {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": entity},
        ensure_ascii=False,
    )


def _tippa_related_links(*exclude: str) -> list[dict]:
    """Shared 'other series' links for SEO tippa pages."""
    all_links = [
        {
            "href": "/tippa-supercross",
            "label": "Tippa Supercross (SX)",
            "blurb": "amerikansk AMA Supercross",
        },
        {
            "href": "/tippa-motocross",
            "label": "Tippa Motocross (MX)",
            "blurb": "Pro Motocross utomhus",
        },
        {
            "href": "/tippa-smx",
            "label": "Tippa SMX",
            "blurb": "SuperMotocross playoffs",
        },
        {
            "href": "/tippa-wsx",
            "label": "Tippa WSX",
            "blurb": "World Supercross Championship",
        },
        {
            "href": "/tippa-mxgp",
            "label": "Tippa MXGP",
            "blurb": "FIM Motocross World Championship",
        },
        {
            "href": "/tippa-mxon",
            "label": "Tippa MXoN",
            "blurb": "Motocross of Nations — tippa länder",
        },
    ]
    skip = set(exclude)
    return [link for link in all_links if link["href"] not in skip]


def _tippa_supercross_page_data() -> dict:
    faq = [
        {
            "q": "Hur tippar jag Supercross (SX)?",
            "a": "Skapa gratis konto på mx-fantasy.se, välj serien Supercross, öppna nästa race och tippa topp 6 i 450 och 250 plus holeshot och wildcard innan deadline.",
            "a_plain": "Skapa gratis konto på mx-fantasy.se, välj serien Supercross, öppna nästa race och tippa topp 6 i 450 och 250 plus holeshot och wildcard innan deadline.",
        },
        {
            "q": "Vad är skillnaden mellan tippa SX och tippa motocross?",
            "a": "Supercross körs oftast i arena med ett huvudrace per klass. Pro Motocross (utomhus-MX) har oftast två heat och overall. I MX Fantasy tippar du inför varje tävling i den serie du följer.",
            "a_plain": "Supercross körs oftast i arena med ett huvudrace per klass. Pro Motocross (utomhus-MX) har oftast två heat och overall. I MX Fantasy tippar du inför varje tävling i den serie du följer.",
        },
        {
            "q": "Kostar det att tippa supercross hos er?",
            "a": "Nej. Konto, tips, ligor och leaderboard är gratis. Du spelar om fantasypoäng — ingen betting.",
            "a_plain": "Nej. Konto, tips, ligor och leaderboard är gratis. Du spelar om fantasypoäng — ingen betting.",
        },
        {
            "q": "När måste SX-tipsen vara inne?",
            "a": "Normalt två timmar före race startar. När tipset låses kan du inte ändra mer. Se deadline i appen för varje race.",
            "a_plain": "Normalt två timmar före race startar. När tipset låses kan du inte ändra mer. Se deadline i appen för varje race.",
        },
        {
            "q": "Kan man tippa både 450 och 250 i Supercross?",
            "a": "Ja. Du tippar topp 6 i båda klasserna (där de finns), plus holeshot och wildcard enligt spelets setup för racehelgen.",
            "a_plain": "Ja. Du tippar topp 6 i båda klasserna (där de finns), plus holeshot och wildcard enligt spelets setup för racehelgen.",
        },
        {
            "q": "Finns det fantasy Supercross på svenska?",
            "a": "Ja — MX Fantasy League är byggt för svenska fans med SV/EN i appen. Den här guiden förklarar hur du tippar SX hos oss.",
            "a_plain": "Ja — MX Fantasy League är byggt för svenska fans med SV/EN i appen. Den här guiden förklarar hur du tippar SX hos oss.",
        },
    ]
    return {
        "path": "/tippa-supercross",
        "series_short": "SX",
        "breadcrumb_name": "Tippa Supercross",
        "seo_title": "Tippa Supercross (SX) — gratis fantasy SX-spel | MX Fantasy League",
        "seo_description": "Hur tippar man Supercross online? Gratis fantasy SX / tippa supercross i MX Fantasy League: topp 6, holeshot och wildcard — utan betting. Guiden för svenska fans.",
        "seo_keywords": (
            "tippa supercross, fantasy supercross, fantasy sx, tippa sx, "
            "supercross fantasy sverige, sx spel, tippa 450 supercross, "
            "gratis fantasy supercross, MX Fantasy League"
        ),
        "h1": "Hur tippar jag Supercross?",
        "lead": (
            "Vill du tippa Supercross (SX) online? I MX Fantasy League tippar du topp 6, "
            "holeshot och wildcard inför amerikanska SX-race — gratis fantasy supercross "
            "utan betting, på mx-fantasy.se."
        ),
        "what_title": "Vad är tippa Supercross / fantasy SX?",
        "what_paragraphs": [
            (
                "Amerikansk Supercross är arenaserien med 450- och 250-klass. "
                "I fantasy SX tippar du vilka förare som placerar sig högst i riktiga race "
                "och får fantasypoäng utifrån hur nära du ligger resultatet."
            ),
            (
                "MX Fantasy League är ett gratis sx-spel för dig som följer sporten i Sverige "
                "(eller internationellt): skapa konto, tippa inför varje racehelg, spela solo "
                "eller i liga med kompisar."
            ),
        ],
        "steps": [
            "<strong class=\"text-white\">Skapa konto</strong> på mx-fantasy.se — gratis.",
            "<strong class=\"text-white\">Välj serien Supercross (SX)</strong> på startsidan.",
            "<strong class=\"text-white\">Öppna nästa race</strong> och sätt topp 6 i 450 och 250.",
            "<strong class=\"text-white\">Lägg till holeshot och wildcard</strong> innan deadline (ofta 2 h före start).",
            "<strong class=\"text-white\">Följ poängen</strong> när race är klart — och utmana i ligor/dueller.",
        ],
        "faq": faq,
        "faq_json": _tippa_serie_faq_json(faq),
        "related_links": _tippa_related_links("/tippa-supercross"),
    }


def _tippa_motocross_page_data() -> dict:
    faq = [
        {
            "q": "Hur tippar jag motocross (Pro MX)?",
            "a": "Skapa gratis konto, välj serien Pro Motocross / MX, öppna nästa racehelg och tippa topp 6, holeshot och wildcard innan deadline.",
            "a_plain": "Skapa gratis konto, välj serien Pro Motocross / MX, öppna nästa racehelg och tippa topp 6, holeshot och wildcard innan deadline.",
        },
        {
            "q": "Vad betyder tippa mx / fantasy motocross?",
            "a": "Du tippar förare i riktiga utomhus-motocrossrace och får fantasypoäng. Det är ett mx-spel för nöje — inte betting om pengar.",
            "a_plain": "Du tippar förare i riktiga utomhus-motocrossrace och får fantasypoäng. Det är ett mx-spel för nöje — inte betting om pengar.",
        },
        {
            "q": "Är Pro Motocross samma sak som Supercross?",
            "a": "Nej. Supercross är oftast arena; Pro Motocross är utomhusbanor med typiskt två heat och overall. Du tippar dem som separata serier i appen.",
            "a_plain": "Nej. Supercross är oftast arena; Pro Motocross är utomhusbanor med typiskt två heat och overall. Du tippar dem som separata serier i appen.",
        },
        {
            "q": "Kostar mx-spelet något?",
            "a": "Nej. Tippa motocross hos MX Fantasy League är gratis — konto, picks och ligor utan kostnad.",
            "a_plain": "Nej. Tippa motocross hos MX Fantasy League är gratis — konto, picks och ligor utan kostnad.",
        },
        {
            "q": "När måste MX-tipsen vara inne?",
            "a": "Normalt två timmar före start. Kolla alltid deadline i appen för just den racehelgen.",
            "a_plain": "Normalt två timmar före start. Kolla alltid deadline i appen för just den racehelgen.",
        },
        {
            "q": "Kan man tippa motocross med vänner?",
            "a": "Ja — skapa eller gå med i en privat liga, jämför säsongspoäng och kör dueller. Eller spela solo mot leaderboarden.",
            "a_plain": "Ja — skapa eller gå med i en privat liga, jämför säsongspoäng och kör dueller. Eller spela solo mot leaderboarden.",
        },
    ]
    return {
        "path": "/tippa-motocross",
        "series_short": "MX",
        "breadcrumb_name": "Tippa Motocross",
        "seo_title": "Tippa motocross (MX) — gratis mx-spel & fantasy MX | MX Fantasy League",
        "seo_description": "Hur tippar man motocross online? Gratis mx-spel / fantasy motocross i MX Fantasy League: tippa Pro MX topp 6, holeshot och wildcard — utan betting.",
        "seo_keywords": (
            "tippa motocross, tippa mx, mx spel, fantasy motocross, fantasy mx, "
            "motocross tippning, tippa pro motocross, gratis mx spel, "
            "motocross spel online, MX Fantasy League"
        ),
        "h1": "Hur tippar jag motocross?",
        "lead": (
            "Vill du tippa motocross online? I MX Fantasy League är mx-spelet gratis fantasy "
            "motocross: tippa topp 6, holeshot och wildcard i amerikanska Pro Motocross — "
            "poäng och ligor utan betting."
        ),
        "what_title": "Vad är tippa mx / fantasy motocross?",
        "what_paragraphs": [
            (
                "Pro Motocross (ofta kallat MX eller utomhus-motocross) körs på jordbanor "
                "ute, vanligtvis med två heat och en overall-placering. I fantasy tippar du "
                "förare inför racehelgen och får fantasypoäng efter resultatet."
            ),
            (
                "Söker du efter mx spel, tippa mx eller motocross tippning på svenska är "
                "MX Fantasy League byggt för just det — i webbläsaren på mobil eller dator."
            ),
        ],
        "steps": [
            "<strong class=\"text-white\">Skapa konto</strong> — gratis på mx-fantasy.se.",
            "<strong class=\"text-white\">Välj Pro Motocross (MX)</strong> som serie.",
            "<strong class=\"text-white\">Öppna nästa racehelg</strong> och tippa topp 6 i klasserna som gäller.",
            "<strong class=\"text-white\">Fyll i holeshot och wildcard</strong> innan deadline.",
            "<strong class=\"text-white\">Samla poäng</strong> och tävla i ligor eller solo.",
        ],
        "faq": faq,
        "faq_json": _tippa_serie_faq_json(faq),
        "related_links": _tippa_related_links("/tippa-motocross"),
    }


def _tippa_smx_page_data() -> dict:
    faq = [
        {
            "q": "Hur tippar jag SMX / SuperMotocross?",
            "a": "Skapa gratis konto på mx-fantasy.se, välj SMX Finals när slutspelet är aktivt, öppna Playoff 1, Playoff 2 eller Finalen och tippa topp 6, holeshot och wildcard innan deadline.",
            "a_plain": "Skapa gratis konto på mx-fantasy.se, välj SMX Finals när slutspelet är aktivt, öppna Playoff 1, Playoff 2 eller Finalen och tippa topp 6, holeshot och wildcard innan deadline.",
        },
        {
            "q": "Vad är skillnaden mellan SX, MX och SMX?",
            "a": "Supercross (SX) är arena, Pro Motocross (MX) är utomhus. SMX är slutspelet efter SX+MX: tre rundor där toppryttare från den kombinerade säsongen gör upp om SMX-titeln.",
            "a_plain": "Supercross (SX) är arena, Pro Motocross (MX) är utomhus. SMX är slutspelet efter SX+MX: tre rundor där toppryttare från den kombinerade säsongen gör upp om SMX-titeln.",
        },
        {
            "q": "Vad betyder 1×, 2× och 3× i SMX?",
            "a": "Playoff 1 ger normala poäng (1×), Playoff 2 dubbla (2×) och SMX Final trippla (3×). I fantasy påverkar multiplikatorn hur mycket race-resultatet väger i tippspelet beroende på hur poängen är uppsatta för den tävlingen.",
            "a_plain": "Playoff 1 ger normala poäng (1×), Playoff 2 dubbla (2×) och SMX Final trippla (3×). I fantasy påverkar multiplikatorn hur mycket race-resultatet väger i tippspelet beroende på hur poängen är uppsatta för den tävlingen.",
        },
        {
            "q": "Kostar det att tippa SMX?",
            "a": "Nej. Konto, tips, ligor och leaderboard är gratis. Ingen betting — bara fantasypoäng.",
            "a_plain": "Nej. Konto, tips, ligor och leaderboard är gratis. Ingen betting — bara fantasypoäng.",
        },
        {
            "q": "När är SMX Playoffs 2026?",
            "a": "Enligt kalendern: Playoff 1 Columbus 12 september, Playoff 2 Carson/LA 19 september, Final Ridgedale 26 september. Se alltid datum och deadline i appen.",
            "a_plain": "Enligt kalendern: Playoff 1 Columbus 12 september, Playoff 2 Carson/LA 19 september, Final Ridgedale 26 september. Se alltid datum och deadline i appen.",
        },
        {
            "q": "Kan man tippa både 450 och 250 i SMX?",
            "a": "Ja. Du tippar topp 6 i klasserna som gäller för racehelgen, plus holeshot och wildcard enligt spelets setup.",
            "a_plain": "Ja. Du tippar topp 6 i klasserna som gäller för racehelgen, plus holeshot och wildcard enligt spelets setup.",
        },
    ]
    return {
        "path": "/tippa-smx",
        "series_short": "SMX",
        "breadcrumb_name": "Tippa SMX",
        "seo_title": "Tippa SMX / SuperMotocross — gratis fantasy SMX-spel | MX Fantasy League",
        "seo_description": (
            "Hur tippar man SuperMotocross (SMX) online? Gratis fantasy SMX-spel i MX Fantasy League: "
            "Playoff 1–2 och Final — topp 6, holeshot och wildcard utan betting."
        ),
        "seo_keywords": (
            "tippa smx, tippa supermotocross, fantasy smx, supermotocross fantasy, "
            "smx playoffs tippning, smx final fantasy, tippa smx sverige, "
            "gratis fantasy supermotocross, MX Fantasy League"
        ),
        "h1": "Hur tippar jag SMX / SuperMotocross?",
        "lead": (
            "Vill du tippa SuperMotocross (SMX) online? I MX Fantasy League tippar du "
            "Playoff 1, Playoff 2 och SMX Final — gratis fantasy utan betting, på mx-fantasy.se."
        ),
        "what_title": "Vad är tippa SMX / fantasy SuperMotocross?",
        "what_paragraphs": [
            (
                "SMX World Championship är slutspelet efter AMA Supercross och Pro Motocross: "
                "tre racehelger där de bästa från den kombinerade säsongen gör upp. "
                "Playoff 2 ger dubbla poäng och Finalen trippla i den officiella SMX-titeln."
            ),
            (
                "I MX Fantasy League tippar du inför varje SMX-runda precis som i SX/MX: "
                "topp 6, holeshot och wildcard. Perfekt om du följer hela amerikanska säsongen "
                "och vill ha ett smx-spel på svenska."
            ),
        ],
        "steps": [
            "<strong class=\"text-white\">Skapa konto</strong> på mx-fantasy.se — gratis.",
            "<strong class=\"text-white\">Välj SMX Finals</strong> när slutspelet är igång (efter Pro Motocross).",
            "<strong class=\"text-white\">Öppna Playoff 1, 2 eller Finalen</strong> och tippa topp 6.",
            "<strong class=\"text-white\">Lägg holeshot och wildcard</strong> innan deadline (ofta 2 h före start).",
            "<strong class=\"text-white\">Följ poängen</strong> — Finalen väger tyngst (3×).",
        ],
        "faq": faq,
        "faq_json": _tippa_serie_faq_json(faq),
        "related_links": _tippa_related_links("/tippa-smx"),
    }


def _tippa_wsx_page_data() -> dict:
    faq = [
        {
            "q": "Hur tippar jag WSX / World Supercross?",
            "a": "Skapa gratis konto, välj serien WSX, öppna nästa GP (t.ex. Canadian GP) och tippa topp 6 i SX1 och SX2 plus holeshot innan deadline.",
            "a_plain": "Skapa gratis konto, välj serien WSX, öppna nästa GP (t.ex. Canadian GP) och tippa topp 6 i SX1 och SX2 plus holeshot innan deadline.",
        },
        {
            "q": "Vad är WSX jämfört med AMA Supercross?",
            "a": "WSX (World Supercross Championship) är FIM:s världscup med internationella GP-rundor och klasserna SX1/SX2. AMA Supercross är den amerikanska arenaserien. I appen tippar du dem som separata serier.",
            "a_plain": "WSX (World Supercross Championship) är FIM:s världscup med internationella GP-rundor och klasserna SX1/SX2. AMA Supercross är den amerikanska arenaserien. I appen tippar du dem som separata serier.",
        },
        {
            "q": "Finns wildcard i WSX-tippningen?",
            "a": "WSX i MX Fantasy är tippa-only för SX1 och SX2 (topp 6 + holeshot). Wildcard-omgången som i SX/MX används inte på samma sätt — se setup i appen per race.",
            "a_plain": "WSX i MX Fantasy är tippa-only för SX1 och SX2 (topp 6 + holeshot). Wildcard-omgången som i SX/MX används inte på samma sätt — se setup i appen per race.",
        },
        {
            "q": "Kostar det att tippa World Supercross?",
            "a": "Nej. Gratis konto, tips och leaderboard — ingen betting.",
            "a_plain": "Nej. Gratis konto, tips och leaderboard — ingen betting.",
        },
        {
            "q": "När måste WSX-tipsen vara inne?",
            "a": "Normalt två timmar före start. Kolla alltid deadline i appen för just det GP:t (tidszonen kan skilja mellan länder).",
            "a_plain": "Normalt två timmar före start. Kolla alltid deadline i appen för just det GP:t (tidszonen kan skilja mellan länder).",
        },
        {
            "q": "Kan man tippa WSX på svenska?",
            "a": "Ja — MX Fantasy League har SV/EN i appen och den här guiden förklarar hur du tippar WSX hos oss.",
            "a_plain": "Ja — MX Fantasy League har SV/EN i appen och den här guiden förklarar hur du tippar WSX hos oss.",
        },
    ]
    return {
        "path": "/tippa-wsx",
        "series_short": "WSX",
        "breadcrumb_name": "Tippa WSX",
        "seo_title": "Tippa WSX / World Supercross — gratis fantasy WSX-spel | MX Fantasy League",
        "seo_description": (
            "Hur tippar man World Supercross (WSX) online? Gratis fantasy WSX-spel i MX Fantasy League: "
            "tippa SX1 och SX2 topp 6 + holeshot — utan betting."
        ),
        "seo_keywords": (
            "tippa wsx, tippa world supercross, fantasy wsx, world supercross fantasy, "
            "wsx tippning, tippa sx1 sx2, fim world supercross, "
            "gratis fantasy wsx, MX Fantasy League"
        ),
        "h1": "Hur tippar jag WSX / World Supercross?",
        "lead": (
            "Vill du tippa World Supercross (WSX) online? I MX Fantasy League tippar du "
            "SX1 och SX2 inför varje GP — gratis fantasy utan betting, på mx-fantasy.se."
        ),
        "what_title": "Vad är tippa WSX / fantasy World Supercross?",
        "what_paragraphs": [
            (
                "World Supercross Championship (WSX) är den internationella FIM-serien med "
                "GP-rundor runt om i världen. Klasserna heter SX1 och SX2. "
                "I fantasy tippar du vilka förare som placerar sig högst och får fantasypoäng."
            ),
            (
                "Söker du fantasy WSX, tippa world supercross eller WSX-spel på svenska är "
                "MX Fantasy League byggt för dig som följer både AMA och världscupen."
            ),
        ],
        "steps": [
            "<strong class=\"text-white\">Skapa konto</strong> — gratis på mx-fantasy.se.",
            "<strong class=\"text-white\">Välj serien WSX</strong> på startsidan.",
            "<strong class=\"text-white\">Öppna nästa GP</strong> och tippa topp 6 i SX1 och SX2.",
            "<strong class=\"text-white\">Välj holeshot</strong> per klass innan deadline.",
            "<strong class=\"text-white\">Följ leaderboard</strong> och utmana i ligor.",
        ],
        "faq": faq,
        "faq_json": _tippa_serie_faq_json(faq),
        "related_links": _tippa_related_links("/tippa-wsx"),
    }


def _tippa_mxgp_page_data() -> dict:
    faq = [
        {
            "q": "Hur tippar jag MXGP / FIM Motocross World Championship?",
            "a": "Skapa gratis konto på mx-fantasy.se, välj serien MXGP när den är öppen, öppna nästa GP och tippa topp 6 i MXGP och MX2 plus holeshot Race 1 och kvalvinnare innan deadline.",
            "a_plain": "Skapa gratis konto på mx-fantasy.se, välj serien MXGP när den är öppen, öppna nästa GP och tippa topp 6 i MXGP och MX2 plus holeshot Race 1 och kvalvinnare innan deadline.",
        },
        {
            "q": "Vad är skillnaden mellan MXGP och amerikansk Pro Motocross?",
            "a": "MXGP är FIM:s världsmästerskap i motocross (MXGP- och MX2-klass) med GP-rundor i Europa och världen. Pro Motocross (MX) är den amerikanska utomhusserien. I appen tippar du dem som separata serier.",
            "a_plain": "MXGP är FIM:s världsmästerskap i motocross (MXGP- och MX2-klass) med GP-rundor i Europa och världen. Pro Motocross (MX) är den amerikanska utomhusserien. I appen tippar du dem som separata serier.",
        },
        {
            "q": "Finns wildcard i MXGP-tippningen?",
            "a": "Nej — MXGP i MX Fantasy är tippa-only: topp 6 per klass, holeshot Race 1 och kvalvinnare (lördag). Ingen wildcard-omgång som i SX/MX.",
            "a_plain": "Nej — MXGP i MX Fantasy är tippa-only: topp 6 per klass, holeshot Race 1 och kvalvinnare (lördag). Ingen wildcard-omgång som i SX/MX.",
        },
        {
            "q": "Kostar det att tippa MXGP?",
            "a": "Nej. Gratis konto, tips och leaderboard — ingen betting.",
            "a_plain": "Nej. Gratis konto, tips och leaderboard — ingen betting.",
        },
        {
            "q": "När öppnar tippa MXGP för alla?",
            "a": "Serien byggs inför 2027-säsongen. Skapa konto nu; när publik tippa slås på syns MXGP på startsidan. Se alltid status och deadline i appen.",
            "a_plain": "Serien byggs inför 2027-säsongen. Skapa konto nu; när publik tippa slås på syns MXGP på startsidan. Se alltid status och deadline i appen.",
        },
        {
            "q": "Kan man tippa både MXGP och MX2?",
            "a": "Ja. Du tippar topp 6 i båda klasserna, plus holeshot Race 1 och kvalvinnare per klass.",
            "a_plain": "Ja. Du tippar topp 6 i båda klasserna, plus holeshot Race 1 och kvalvinnare per klass.",
        },
    ]
    return {
        "path": "/tippa-mxgp",
        "series_short": "MXGP",
        "breadcrumb_name": "Tippa MXGP",
        "seo_title": "Tippa MXGP — gratis fantasy MXGP / FIM Motocross | MX Fantasy League",
        "seo_description": (
            "Hur tippar man MXGP online? Gratis fantasy MXGP-spel i MX Fantasy League: "
            "tippa MXGP och MX2 topp 6, holeshot Race 1 och kval — utan betting."
        ),
        "seo_keywords": (
            "tippa mxgp, fantasy mxgp, tippa fim motocross, mxgp fantasy sverige, "
            "tippa mx2, fim mxgp tippning, gratis fantasy mxgp, "
            "motocross world championship fantasy, MX Fantasy League"
        ),
        "h1": "Hur tippar jag MXGP?",
        "lead": (
            "Vill du tippa MXGP / FIM Motocross World Championship online? "
            "I MX Fantasy League tippar du MXGP och MX2 inför varje GP — "
            "gratis fantasy utan betting, på mx-fantasy.se."
        ),
        "what_title": "Vad är tippa MXGP / fantasy FIM Motocross?",
        "what_paragraphs": [
            (
                "MXGP är världsmästerskapet i motocross under FIM: GP-helger runt om i världen "
                "med klasserna MXGP och MX2. I fantasy tippar du vilka förare som placerar sig "
                "högst och får fantasypoäng efter resultatet."
            ),
            (
                "Söker du fantasy MXGP, tippa mxgp eller FIM motocross-spel på svenska är "
                "MX Fantasy League byggt för dig som följer både AMA och världscupen — "
                "inklusive Uddevalla och övriga GP-banor."
            ),
        ],
        "steps": [
            "<strong class=\"text-white\">Skapa konto</strong> — gratis på mx-fantasy.se.",
            "<strong class=\"text-white\">Välj serien MXGP</strong> när tippa är öppen för säsongen.",
            "<strong class=\"text-white\">Öppna nästa GP</strong> och tippa topp 6 i MXGP och MX2.",
            "<strong class=\"text-white\">Välj holeshot Race 1 och kvalvinnare</strong> per klass innan deadline.",
            "<strong class=\"text-white\">Följ leaderboard</strong> och utmana i ligor.",
        ],
        "faq": faq,
        "faq_json": _tippa_serie_faq_json(faq),
        "related_links": _tippa_related_links("/tippa-mxgp"),
    }


def _tippa_mxon_page_data() -> dict:
    faq = [
        {
            "q": "Hur tippar jag MXoN / Motocross of Nations?",
            "a": "Skapa gratis konto, välj Motocross of Nations (MXON), öppna tippa och rangordna topp 5 nationer innan deadline (före lördagens MXGP-kval).",
            "a_plain": "Skapa gratis konto, välj Motocross of Nations (MXON), öppna tippa och rangordna topp 5 nationer innan deadline (före lördagens MXGP-kval).",
        },
        {
            "q": "Vad tippar man i MXoN jämfört med vanlig MXGP?",
            "a": "I MXoN tippar du länder — inte individuella förare i topp 6. Du sätter topp 5 nationer utifrån provisional entry (t.ex. 33 lag). Poäng ges efter hur nära din lista ligger slutställningen.",
            "a_plain": "I MXoN tippar du länder — inte individuella förare i topp 6. Du sätter topp 5 nationer utifrån provisional entry (t.ex. 33 lag). Poäng ges efter hur nära din lista ligger slutställningen.",
        },
        {
            "q": "När är Motocross of Nations 2026?",
            "a": "MXoN 2026 körs i Ernée, Frankrike (2–4 oktober). Tippa låses före lördagens MXGP-kval (~14:30 lokal tid). Race-dagen är söndag 4 oktober (Race 1 ~13:10). Se alltid exakt deadline i appen.",
            "a_plain": "MXoN 2026 körs i Ernée, Frankrike (2–4 oktober). Tippa låses före lördagens MXGP-kval (~14:30 lokal tid). Race-dagen är söndag 4 oktober (Race 1 ~13:10). Se alltid exakt deadline i appen.",
        },
        {
            "q": "Kostar det att tippa Motocross of Nations?",
            "a": "Nej. Gratis konto, tips och leaderboard — ingen betting.",
            "a_plain": "Nej. Gratis konto, tips och leaderboard — ingen betting.",
        },
        {
            "q": "Finns Sverige med i tipplistan?",
            "a": "Ja om Sverige står på den provisional entry-listan som seedats i spelet. Du tippar bland de aktiva nationerna i appen (inkl. TBA-platser där laget inte spärrats).",
            "a_plain": "Ja om Sverige står på den provisional entry-listan som seedats i spelet. Du tippar bland de aktiva nationerna i appen (inkl. TBA-platser där laget inte spärrats).",
        },
        {
            "q": "Är MXoN samma serie som MXGP?",
            "a": "Nej. MXGP är säsongens världsmästerskap; Motocross of Nations är det årliga landslagetseventet. I MX Fantasy tippar du dem som separata grejer.",
            "a_plain": "Nej. MXGP är säsongens världsmästerskap; Motocross of Nations är det årliga landslagetseventet. I MX Fantasy tippar du dem som separata grejer.",
        },
    ]
    return {
        "path": "/tippa-mxon",
        "series_short": "MXoN",
        "breadcrumb_name": "Tippa MXoN",
        "seo_title": "Tippa MXoN / Motocross of Nations — gratis fantasy | MX Fantasy League",
        "seo_description": (
            "Hur tippar man Motocross of Nations (MXoN) online? Gratis fantasy i MX Fantasy League: "
            "tippa topp 5 nationer i Ernée 2026 — utan betting."
        ),
        "seo_keywords": (
            "tippa mxon, tippa motocross of nations, fantasy mxon, "
            "motocross of nations tippning, tippa länder mxon, ernée 2026 fantasy, "
            "gratis fantasy mxon, MX Fantasy League"
        ),
        "h1": "Hur tippar jag MXoN / Motocross of Nations?",
        "lead": (
            "Vill du tippa Motocross of Nations (MXoN) online? I MX Fantasy League tippar du "
            "topp 5 nationer inför Ernée 2026 — gratis fantasy utan betting, på mx-fantasy.se."
        ),
        "what_title": "Vad är tippa MXoN / fantasy Motocross of Nations?",
        "what_paragraphs": [
            (
                "Motocross of Nations är FIM:s årliga landslagstävling — lag med MXGP-, MX2- och "
                "OPEN-förare gör upp om Nations-titeln. I fantasy tippar du vilka länder som "
                "placerar sig högst, inte individuella topp 6 som i vanlig GP-tippning."
            ),
            (
                "Söker du tippa mxon, fantasy Motocross of Nations eller landslagstippning på "
                "svenska är MX Fantasy League byggt för just det engångseventet — separat "
                "leaderboard från AMA och MXGP."
            ),
        ],
        "steps": [
            "<strong class=\"text-white\">Skapa konto</strong> — gratis på mx-fantasy.se.",
            "<strong class=\"text-white\">Välj Motocross of Nations (MXON)</strong> på startsidan.",
            "<strong class=\"text-white\">Öppna tippa</strong> och rangordna dina topp 5 nationer.",
            "<strong class=\"text-white\">Spara innan deadline</strong> (före MXGP-kval lördag).",
            "<strong class=\"text-white\">Följ MXoN-leaderboard</strong> när resultaten är inne.",
        ],
        "faq": faq,
        "faq_json": _tippa_serie_faq_json(faq),
        "related_links": _tippa_related_links("/tippa-mxon"),
    }
