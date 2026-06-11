from datetime import datetime
from django.http import HttpResponse


def file_download_response(
    buffer,
    filename_prefix,
    content_type,
    extension,
):

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    filename = f"{filename_prefix}_{timestamp}.{extension}"

    response = HttpResponse(
        buffer.getvalue(),
        content_type=content_type
    )

    response["Content-Disposition"] = (
        f'attachment; filename="{filename}"'
    )

    return response