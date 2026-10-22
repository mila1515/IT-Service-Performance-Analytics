"""Archive portable sans écriture sur les fichiers sources."""


import io
import json
import zipfile

from src.etape4_visualiser.graphiques import apply_filters, chart_data
from src.etape4_visualiser.preparation import prepare


def project_archive(source_bytes, cleaned, rejects, report, versions):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("data/raw/source.csv", source_bytes)
        archive.writestr("data/processed/current.csv", cleaned.to_csv(index=False))
        archive.writestr("data/rejects/current.csv", rejects.to_csv(index=False))
        archive.writestr("reports/project.json", json.dumps(report, ensure_ascii=False, indent=2))
        if "repetitions" in report:
            archive.writestr("reports/repetitions.json", json.dumps(report["repetitions"], ensure_ascii=False, indent=2))
        sections = ["# Rapport d'analyse", "", f"Projet : {report['cadrage'].get('project_name', '')}",
                    f"Source : {report['source']}", f"Objectif : {report['objectif']}",
                    f"Décision attendue : {report['cadrage'].get('expected_decision', '')}",
                    f"Décision utilisateur : {report['decision']}",
                    f"Justification : {report['justification_decision']}", "",
                    "## Constats, limites et recommandations", report["conclusions"], "",
                    "Les détails des règles, audits, statistiques et transformations sont dans project.json.",
                    "Les données originales et les rejets peuvent contenir des données sensibles."]
        archive.writestr("reports/summary.md", "\n".join(sections))
        for index, version in enumerate(versions, start=1):
            folder = f"history/v{index:03d}"
            archive.writestr(f"{folder}/cleaned.csv", version["cleaned"])
            archive.writestr(f"{folder}/rejects.csv", version["rejects"])
            archive.writestr(f"{folder}/recipe.json", json.dumps(version["recipe"], ensure_ascii=False, indent=2))
        config = report["dashboard"]
        if config["charts"]:
            prepared, _ = prepare(cleaned, config["roles"], config["dayfirst"])
            filtered = apply_filters(prepared, config["filters"])
            for index, spec in enumerate(config["charts"], start=1):
                frame, _ = chart_data(apply_filters(filtered, spec["filters"]), spec)
                archive.writestr(f"reports/dashboard/chart_{index:03d}.csv", frame.to_csv(index=False))
        archive.writestr("README.txt", "Archive d'un projet à une seule source CSV. Les recettes, audits et versions sont conservés.\n"
                         "Les numéros source désignent les enregistrements hors en-tête.\n"
                         "Les CSV de rejets ont deux lignes d'en-tête pour distinguer traçabilité et données source.\n"
                         "Cette archive est consultable hors application ; la restauration automatique d'une session complète n'est pas encore disponible.\n")
    return buffer.getvalue()
