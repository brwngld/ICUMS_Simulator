from django.db import migrations


def infer_layouts(apps, schema_editor):
    ScenarioDocument = apps.get_model("scenarios", "ScenarioDocument")
    for document in ScenarioDocument.objects.filter(pdf_layout="generic"):
        label = f"{document.document_type} {document.title}".lower()
        if "bill of lading" in label or " b/l" in label:
            document.pdf_layout = "bill_of_lading"
        elif "invoice" in label:
            document.pdf_layout = "commercial_invoice"
        elif "packing" in label and "list" in label:
            document.pdf_layout = "packing_list"
        else:
            continue
        document.save(update_fields=("pdf_layout",))


class Migration(migrations.Migration):
    dependencies = [("scenarios", "0005_scenariodocument_pdf_layout")]
    operations = [migrations.RunPython(infer_layouts, migrations.RunPython.noop)]
