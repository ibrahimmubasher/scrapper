import io


def dataframe_to_excel_buffer(df):

    output = io.BytesIO()

    df.to_excel(
        output,
        index=False,
        engine="openpyxl"
    )

    output.seek(0)

    return output


def dataframe_to_csv_buffer(df):

    output = io.StringIO()

    df.to_csv(
        output,
        index=False
    )

    output.seek(0)

    return output