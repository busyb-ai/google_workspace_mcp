"""
Google Sheets MCP Tools

This module provides MCP tools for interacting with Google Sheets API.
"""

import logging
import asyncio
from typing import List, Optional, Dict, Any

from auth.service_decorator import require_google_service
from core.server import server
from core.utils import handle_http_errors
from core.comments import create_comment_tools

# Configure module logger
logger = logging.getLogger(__name__)


@server.tool()
@handle_http_errors("list_spreadsheets", is_read_only=True, service_type="sheets")
@require_google_service("drive", "drive_read")
async def list_spreadsheets(
    service,
    user_google_email: str,
    max_results: int = 25,
) -> str:
    """
    Lists spreadsheets from Google Drive that the user has access to.

    Args:
        user_google_email (str): The user's Google email address. Required.
        max_results (int): Maximum number of spreadsheets to return. Defaults to 25.

    Returns:
        str: A formatted list of spreadsheet files (name, ID, modified time).
    """
    logger.info(f"[list_spreadsheets] Invoked. Email: '{user_google_email}'")

    files_response = await asyncio.to_thread(
        service.files()
        .list(
            q="mimeType='application/vnd.google-apps.spreadsheet'",
            pageSize=max_results,
            fields="files(id,name,modifiedTime,webViewLink)",
            orderBy="modifiedTime desc",
        )
        .execute
    )

    files = files_response.get("files", [])
    if not files:
        return f"No spreadsheets found for {user_google_email}."

    spreadsheets_list = [
        f"- \"{file['name']}\" (ID: {file['id']}) | Modified: {file.get('modifiedTime', 'Unknown')} | Link: {file.get('webViewLink', 'No link')}"
        for file in files
    ]

    text_output = (
        f"Successfully listed {len(files)} spreadsheets for {user_google_email}:\n"
        + "\n".join(spreadsheets_list)
    )

    logger.info(f"Successfully listed {len(files)} spreadsheets for {user_google_email}.")
    return text_output


@server.tool()
@handle_http_errors("get_spreadsheet_info", is_read_only=True, service_type="sheets")
@require_google_service("sheets", "sheets_read")
async def get_spreadsheet_info(
    service,
    user_google_email: str,
    spreadsheet_id: str,
) -> str:
    """
    Gets information about a specific spreadsheet including its sheets.

    Args:
        user_google_email (str): The user's Google email address. Required.
        spreadsheet_id (str): The ID of the spreadsheet to get info for. Required.

    Returns:
        str: Formatted spreadsheet information including title and sheets list.
    """
    logger.info(f"[get_spreadsheet_info] Invoked. Email: '{user_google_email}', Spreadsheet ID: {spreadsheet_id}")

    spreadsheet = await asyncio.to_thread(
        service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute
    )

    title = spreadsheet.get("properties", {}).get("title", "Unknown")
    sheets = spreadsheet.get("sheets", [])

    sheets_info = []
    for sheet in sheets:
        sheet_props = sheet.get("properties", {})
        sheet_name = sheet_props.get("title", "Unknown")
        sheet_id = sheet_props.get("sheetId", "Unknown")
        grid_props = sheet_props.get("gridProperties", {})
        rows = grid_props.get("rowCount", "Unknown")
        cols = grid_props.get("columnCount", "Unknown")

        sheets_info.append(
            f"  - \"{sheet_name}\" (ID: {sheet_id}) | Size: {rows}x{cols}"
        )

    text_output = (
        f"Spreadsheet: \"{title}\" (ID: {spreadsheet_id})\n"
        f"Sheets ({len(sheets)}):\n"
        + "\n".join(sheets_info) if sheets_info else "  No sheets found"
    )

    logger.info(f"Successfully retrieved info for spreadsheet {spreadsheet_id} for {user_google_email}.")
    return text_output


@server.tool()
@handle_http_errors("read_sheet_values", is_read_only=True, service_type="sheets")
@require_google_service("sheets", "sheets_read")
async def read_sheet_values(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    range_name: str = "A1:Z1000",
) -> str:
    """
    Reads values from a specific range in a Google Sheet.

    Args:
        user_google_email (str): The user's Google email address. Required.
        spreadsheet_id (str): The ID of the spreadsheet. Required.
        range_name (str): The range to read (e.g., "Sheet1!A1:D10", "A1:D10"). Defaults to "A1:Z1000".

    Returns:
        str: The formatted values from the specified range.
    """
    logger.info(f"[read_sheet_values] Invoked. Email: '{user_google_email}', Spreadsheet: {spreadsheet_id}, Range: {range_name}")

    result = await asyncio.to_thread(
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_name)
        .execute
    )

    values = result.get("values", [])
    if not values:
        return f"No data found in range '{range_name}' for {user_google_email}."

    # Format the output as a readable table
    formatted_rows = []
    for i, row in enumerate(values, 1):
        # Pad row with empty strings to show structure
        padded_row = row + [""] * max(0, len(values[0]) - len(row)) if values else row
        formatted_rows.append(f"Row {i:2d}: {padded_row}")

    text_output = (
        f"Successfully read {len(values)} rows from range '{range_name}' in spreadsheet {spreadsheet_id} for {user_google_email}:\n"
        + "\n".join(formatted_rows[:50])  # Limit to first 50 rows for readability
        + (f"\n... and {len(values) - 50} more rows" if len(values) > 50 else "")
    )

    logger.info(f"Successfully read {len(values)} rows for {user_google_email}.")
    return text_output


@server.tool()
@handle_http_errors("modify_sheet_values", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def modify_sheet_values(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    range_name: str,
    values: Optional[List[List[str]]] = None,
    value_input_option: str = "USER_ENTERED",
    clear_values: bool = False,
) -> str:
    """
    Modifies values in a specific range of a Google Sheet - can write, update, or clear values.

    Args:
        user_google_email (str): The user's Google email address. Required.
        spreadsheet_id (str): The ID of the spreadsheet. Required.
        range_name (str): The range to modify (e.g., "Sheet1!A1:D10", "A1:D10"). Required.
        values (Optional[List[List[str]]]): 2D array of values to write/update. Required unless clear_values=True.
        value_input_option (str): How to interpret input values ("RAW" or "USER_ENTERED"). Defaults to "USER_ENTERED".
        clear_values (bool): If True, clears the range instead of writing values. Defaults to False.

    Returns:
        str: Confirmation message of the successful modification operation.
    """
    operation = "clear" if clear_values else "write"
    logger.info(f"[modify_sheet_values] Invoked. Operation: {operation}, Email: '{user_google_email}', Spreadsheet: {spreadsheet_id}, Range: {range_name}")

    if not clear_values and not values:
        raise Exception("Either 'values' must be provided or 'clear_values' must be True.")

    if clear_values:
        result = await asyncio.to_thread(
            service.spreadsheets()
            .values()
            .clear(spreadsheetId=spreadsheet_id, range=range_name)
            .execute
        )

        cleared_range = result.get("clearedRange", range_name)
        text_output = f"Successfully cleared range '{cleared_range}' in spreadsheet {spreadsheet_id} for {user_google_email}."
        logger.info(f"Successfully cleared range '{cleared_range}' for {user_google_email}.")
    else:
        body = {"values": values}

        result = await asyncio.to_thread(
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=spreadsheet_id,
                range=range_name,
                valueInputOption=value_input_option,
                body=body,
            )
            .execute
        )

        updated_cells = result.get("updatedCells", 0)
        updated_rows = result.get("updatedRows", 0)
        updated_columns = result.get("updatedColumns", 0)

        text_output = (
            f"Successfully updated range '{range_name}' in spreadsheet {spreadsheet_id} for {user_google_email}. "
            f"Updated: {updated_cells} cells, {updated_rows} rows, {updated_columns} columns."
        )
        logger.info(f"Successfully updated {updated_cells} cells for {user_google_email}.")

    return text_output


@server.tool()
@handle_http_errors("create_spreadsheet", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def create_spreadsheet(
    service,
    user_google_email: str,
    title: str,
    sheet_names: Optional[List[str]] = None,
) -> str:
    """
    Creates a new Google Spreadsheet.

    Args:
        user_google_email (str): The user's Google email address. Required.
        title (str): The title of the new spreadsheet. Required.
        sheet_names (Optional[List[str]]): List of sheet names to create. If not provided, creates one sheet with default name.

    Returns:
        str: Information about the newly created spreadsheet including ID and URL.
    """
    logger.info(f"[create_spreadsheet] Invoked. Email: '{user_google_email}', Title: {title}")

    spreadsheet_body = {
        "properties": {
            "title": title
        }
    }

    if sheet_names:
        spreadsheet_body["sheets"] = [
            {"properties": {"title": sheet_name}} for sheet_name in sheet_names
        ]

    spreadsheet = await asyncio.to_thread(
        service.spreadsheets().create(body=spreadsheet_body).execute
    )

    spreadsheet_id = spreadsheet.get("spreadsheetId")
    spreadsheet_url = spreadsheet.get("spreadsheetUrl")

    text_output = (
        f"Successfully created spreadsheet '{title}' for {user_google_email}. "
        f"ID: {spreadsheet_id} | URL: {spreadsheet_url}"
    )

    logger.info(f"Successfully created spreadsheet for {user_google_email}. ID: {spreadsheet_id}")
    return text_output


@server.tool()
@handle_http_errors("create_sheet", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def create_sheet(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    sheet_name: str,
) -> str:
    """
    Creates a new sheet within an existing spreadsheet.

    Args:
        user_google_email (str): The user's Google email address. Required.
        spreadsheet_id (str): The ID of the spreadsheet. Required.
        sheet_name (str): The name of the new sheet. Required.

    Returns:
        str: Confirmation message of the successful sheet creation.
    """
    logger.info(f"[create_sheet] Invoked. Email: '{user_google_email}', Spreadsheet: {spreadsheet_id}, Sheet: {sheet_name}")

    request_body = {
        "requests": [
            {
                "addSheet": {
                    "properties": {
                        "title": sheet_name
                    }
                }
            }
        ]
    }

    response = await asyncio.to_thread(
        service.spreadsheets()
        .batchUpdate(spreadsheetId=spreadsheet_id, body=request_body)
        .execute
    )

    sheet_id = response["replies"][0]["addSheet"]["properties"]["sheetId"]

    text_output = (
        f"Successfully created sheet '{sheet_name}' (ID: {sheet_id}) in spreadsheet {spreadsheet_id} for {user_google_email}."
    )

    logger.info(f"Successfully created sheet for {user_google_email}. Sheet ID: {sheet_id}")
    return text_output


@server.tool()
@handle_http_errors("batch_get_sheet_values", is_read_only=True, service_type="sheets")
@require_google_service("sheets", "sheets_read")
async def batch_get_sheet_values(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    ranges: List[str],
    major_dimension: Optional[str] = None,
) -> str:
    """
    Reads values from multiple ranges in a Google Sheet (A1 notation).

    Args:
        user_google_email: The user's Google email address.
        spreadsheet_id: The ID of the spreadsheet.
        ranges: List of A1 ranges to read (e.g., ["Sheet1!A1:D10", "Sheet2!A1:B5"]).
        major_dimension: Optional. "ROWS" or "COLUMNS".
    """
    logger.info(f"[batch_get_sheet_values] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, Ranges={len(ranges)}")

    params: Dict[str, Any] = {"spreadsheetId": spreadsheet_id, "ranges": ranges}
    if major_dimension:
        params["majorDimension"] = major_dimension

    result = await asyncio.to_thread(
        service.spreadsheets().values().batchGet(**params).execute
    )

    value_ranges = result.get("valueRanges", [])
    parts = []
    for vr in value_ranges:
        rng = vr.get("range", "?")
        values = vr.get("values", [])
        parts.append(f"- {rng}: {len(values)} rows")

    return (
        f"Successfully read {len(value_ranges)} ranges from spreadsheet {spreadsheet_id} for {user_google_email}:\n"
        + "\n".join(parts)
    )


@server.tool()
@handle_http_errors("append_sheet_values", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def append_sheet_values(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    range_name: str,
    values: List[List[Any]],
    value_input_option: str = "USER_ENTERED",
    insert_data_option: str = "INSERT_ROWS",
    include_values_in_response: bool = False,
) -> str:
    """
    Appends rows to the end of a table/range.

    Args:
        range_name: The A1 range to target (e.g., "Sheet1!A1").
        values: 2D array of rows to append.
        value_input_option: "RAW" or "USER_ENTERED".
        insert_data_option: "OVERWRITE" or "INSERT_ROWS".
        include_values_in_response: Whether to return the appended values in response.
    """
    logger.info(f"[append_sheet_values] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, Range={range_name}, Rows={len(values)}")

    body = {"values": values}
    result = await asyncio.to_thread(
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption=value_input_option,
            insertDataOption=insert_data_option,
            includeValuesInResponse=include_values_in_response,
            body=body,
        )
        .execute
    )

    updates = result.get("updates", {})
    updated_rows = updates.get("updatedRows", 0)
    updated_cells = updates.get("updatedCells", 0)
    updated_range = updates.get("updatedRange", range_name)

    return (
        f"Appended {updated_rows} rows ({updated_cells} cells) to '{updated_range}' in spreadsheet {spreadsheet_id} for {user_google_email}."
    )


@server.tool()
@handle_http_errors("batch_update_sheet_values", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def batch_update_sheet_values(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    data: List[Dict[str, Any]],
    value_input_option: str = "USER_ENTERED",
) -> str:
    """
    Batch update multiple A1 ranges with values.

    Args:
        data: List of {"range": str, "values": List[List[Any]]}
    """
    logger.info(f"[batch_update_sheet_values] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, Ranges={len(data)}")

    body = {"valueInputOption": value_input_option, "data": data}
    result = await asyncio.to_thread(
        service.spreadsheets().values().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute
    )

    total_cells = result.get("totalUpdatedCells", 0)
    total_rows = result.get("totalUpdatedRows", 0)
    total_ranges = len(data)
    return (
        f"Batch updated {total_ranges} ranges with {total_rows} rows ({total_cells} cells) in spreadsheet {spreadsheet_id} for {user_google_email}."
    )


@server.tool()
@handle_http_errors("sheets_batch_update_requests", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def sheets_batch_update_requests(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    requests: List[Dict[str, Any]],
    include_spreadsheet_in_response: bool = False,
) -> str:
    """
    Executes arbitrary Sheets batchUpdate requests for advanced scenarios.

    Args:
        requests: A list of Sheets API requests (repeatCell, updateSheetProperties, addNamedRange, etc.).
        include_spreadsheet_in_response: Whether to include the spreadsheet in the reply.
    """
    logger.info(f"[sheets_batch_update_requests] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, Requests={len(requests)}")

    body = {
        "requests": requests,
        "includeSpreadsheetInResponse": include_spreadsheet_in_response,
    }

    result = await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute
    )

    replies = result.get("replies", [])
    return f"Executed {len(requests)} request(s); received {len(replies)} repl(ies) for spreadsheet {spreadsheet_id}."


@server.tool()
@handle_http_errors("format_cells", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def format_cells(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    grid_range: Dict[str, Any],
    cell_format: Dict[str, Any],
    fields: str,
) -> str:
    """
    Applies formatting to a grid range using repeatCell.

    Args:
        grid_range: GridRange dict with sheetId and indexes.
        cell_format: CellFormat dict per Sheets API.
        fields: Fields mask (e.g., "userEnteredFormat(backgroundColor,textFormat)").
    """
    logger.info(f"[format_cells] Email='{user_google_email}', Spreadsheet={spreadsheet_id}")

    requests = [
        {
            "repeatCell": {
                "range": grid_range,
                "cell": {"userEnteredFormat": cell_format},
                "fields": fields,
            }
        }
    ]

    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )

    return "Applied cell formatting successfully."


@server.tool()
@handle_http_errors("set_sheet_properties", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def set_sheet_properties(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    sheet_id: int,
    title: Optional[str] = None,
    grid_properties: Optional[Dict[str, Any]] = None,
    tab_color: Optional[Dict[str, float]] = None,
    hidden: Optional[bool] = None,
    index: Optional[int] = None,
) -> str:
    """
    Updates sheet properties (title, grid size, frozen rows/cols, tab color, hidden, index).
    """
    logger.info(f"[set_sheet_properties] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, SheetId={sheet_id}")

    props: Dict[str, Any] = {"sheetId": sheet_id}
    fields: List[str] = []

    if title is not None:
        props["title"] = title
        fields.append("title")
    if grid_properties is not None:
        props["gridProperties"] = grid_properties
        fields.append("gridProperties")
    if tab_color is not None:
        props["tabColor"] = tab_color
        fields.append("tabColor")
    if hidden is not None:
        props["hidden"] = hidden
        fields.append("hidden")
    if index is not None:
        props["index"] = index
        fields.append("index")

    if not fields:
        return "No properties provided to update."

    requests = [
        {
            "updateSheetProperties": {
                "properties": props,
                "fields": ",".join(fields),
            }
        }
    ]

    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )

    return f"Updated sheet properties ({', '.join(fields)}) for sheetId {sheet_id}."


@server.tool()
@handle_http_errors("add_named_range", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def add_named_range(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    name: str,
    grid_range: Dict[str, Any],
) -> str:
    """Creates a named range."""
    logger.info(f"[add_named_range] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, Name={name}")

    requests = [
        {
            "addNamedRange": {
                "namedRange": {
                    "name": name,
                    "range": grid_range,
                }
            }
        }
    ]

    result = await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    nr_id = result.get("replies", [{}])[0].get("addNamedRange", {}).get("namedRange", {}).get("namedRangeId")
    return f"Added named range '{name}' with id {nr_id}."


@server.tool()
@handle_http_errors("delete_named_range", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def delete_named_range(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    named_range_id: str,
) -> str:
    """Deletes a named range by ID."""
    logger.info(f"[delete_named_range] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, NamedRangeId={named_range_id}")

    requests = [{"deleteNamedRange": {"namedRangeId": named_range_id}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return f"Deleted named range {named_range_id}."


@server.tool()
@handle_http_errors("set_data_validation", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def set_data_validation(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    grid_range: Dict[str, Any],
    rule: Dict[str, Any],
) -> str:
    """
    Sets data validation for a grid range.

    Args:
        rule: DataValidationRule dict (e.g., list rule, number rule).
    """
    logger.info(f"[set_data_validation] Email='{user_google_email}', Spreadsheet={spreadsheet_id}")

    requests = [
        {
            "setDataValidation": {
                "range": grid_range,
                "rule": rule,
            }
        }
    ]

    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )

    return "Applied data validation rule."


@server.tool()
@handle_http_errors("add_conditional_format_rule", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def add_conditional_format_rule(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    rule: Dict[str, Any],
    index: Optional[int] = None,
) -> str:
    """
    Adds a conditional format rule to a sheet.

    Args:
        rule: ConditionalFormatRule dict.
        index: Optional insertion index.
    """
    logger.info(f"[add_conditional_format_rule] Email='{user_google_email}', Spreadsheet={spreadsheet_id}")

    requests = [
        {
            "addConditionalFormatRule": {
                "rule": rule,
                **({"index": index} if index is not None else {}),
            }
        }
    ]

    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )

    return "Added conditional format rule."


@server.tool()
@handle_http_errors("delete_conditional_format_rule", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def delete_conditional_format_rule(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    sheet_id: int,
    index: int,
) -> str:
    """Deletes a conditional format rule by index."""
    logger.info(f"[delete_conditional_format_rule] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, SheetId={sheet_id}, Index={index}")

    requests = [
        {"deleteConditionalFormatRule": {"index": index, "sheetId": sheet_id}}
    ]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return f"Deleted conditional format rule at index {index} on sheetId {sheet_id}."


@server.tool()
@handle_http_errors("merge_cells", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def merge_cells(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    grid_range: Dict[str, Any],
    merge_type: str = "MERGE_ALL",
) -> str:
    """Merges cells in a given GridRange. merge_type: MERGE_ALL, MERGE_COLUMNS, MERGE_ROWS."""
    logger.info(f"[merge_cells] Email='{user_google_email}', Spreadsheet={spreadsheet_id}")

    requests = [{"mergeCells": {"range": grid_range, "mergeType": merge_type}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return "Merged cells."


@server.tool()
@handle_http_errors("unmerge_cells", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def unmerge_cells(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    grid_range: Dict[str, Any],
) -> str:
    """Unmerges cells in a given GridRange."""
    logger.info(f"[unmerge_cells] Email='{user_google_email}', Spreadsheet={spreadsheet_id}")

    requests = [{"unmergeCells": {"range": grid_range}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return "Unmerged cells."


@server.tool()
@handle_http_errors("sort_range", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def sort_range(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    grid_range: Dict[str, Any],
    sort_specs: List[Dict[str, Any]],
) -> str:
    """
    Sorts a range using provided sort specifications.

    Args:
        sort_specs: List of SortSpec ({"dimensionIndex": int, "sortOrder": "ASCENDING"|"DESCENDING"}).
    """
    logger.info(f"[sort_range] Email='{user_google_email}', Spreadsheet={spreadsheet_id}")

    requests = [{"sortRange": {"range": grid_range, "sortSpecs": sort_specs}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return "Sorted the specified range."


@server.tool()
@handle_http_errors("auto_resize_dimensions", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def auto_resize_dimensions(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    sheet_id: int,
    dimension: str = "COLUMNS",
    start_index: int = 0,
    end_index: Optional[int] = None,
) -> str:
    """
    Auto-resizes rows or columns in the specified index range.

    Args:
        dimension: "COLUMNS" or "ROWS".
    """
    logger.info(f"[auto_resize_dimensions] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, SheetId={sheet_id}")

    dim_range: Dict[str, Any] = {
        "sheetId": sheet_id,
        "dimension": dimension,
        "startIndex": start_index,
    }
    if end_index is not None:
        dim_range["endIndex"] = end_index

    requests = [{"autoResizeDimensions": {"dimensions": dim_range}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return f"Auto-resized {dimension.lower()} from {start_index} to {end_index if end_index is not None else 'end'}."


@server.tool()
@handle_http_errors("create_spreadsheet_detailed", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def create_spreadsheet_detailed(
    service,
    user_google_email: str,
    title: str,
    sheets: Optional[List[Dict[str, Any]]] = None,
    locale: Optional[str] = None,
    time_zone: Optional[str] = None,
    initial_values: Optional[Dict[str, List[List[Any]]]] = None,
    post_create_requests: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """
    Creates a spreadsheet with detailed properties and optional initial values per sheet.

    Args:
        sheets: List of sheet definitions (each may include properties, basic formatting via bandedRanges/conditional rules, etc.).
        initial_values: Mapping of sheet title -> 2D values to write starting at A1 after creation.
    """
    logger.info(f"[create_spreadsheet_detailed] Email='{user_google_email}', Title='{title}'")

    body: Dict[str, Any] = {"properties": {"title": title}}
    if locale:
        body["properties"]["locale"] = locale
    if time_zone:
        body["properties"]["timeZone"] = time_zone
    if sheets:
        body["sheets"] = sheets

    spreadsheet = await asyncio.to_thread(
        service.spreadsheets().create(body=body).execute
    )

    spreadsheet_id = spreadsheet.get("spreadsheetId")
    spreadsheet_url = spreadsheet.get("spreadsheetUrl")

    # If initial values provided, batch write them per sheet
    if initial_values:
        data_payload: List[Dict[str, Any]] = []
        for sheet_title, values in initial_values.items():
            data_payload.append({
                "range": f"{sheet_title}!A1",
                "values": values,
            })
        if data_payload:
            await asyncio.to_thread(
                service.spreadsheets().values().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={"valueInputOption": "USER_ENTERED", "data": data_payload},
                ).execute
            )

    # Execute any post-create requests
    if post_create_requests:
        await asyncio.to_thread(
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": post_create_requests},
            ).execute
        )

    return (
        f"Created detailed spreadsheet '{title}'. ID: {spreadsheet_id} | URL: {spreadsheet_url}"
        + (" with initial values." if initial_values else ".")
    )


# Create comment management tools for sheets
_comment_tools = create_comment_tools("spreadsheet", "spreadsheet_id")

# Extract and register the functions
read_sheet_comments = _comment_tools['read_comments']
create_sheet_comment = _comment_tools['create_comment']
reply_to_sheet_comment = _comment_tools['reply_to_comment']
resolve_sheet_comment = _comment_tools['resolve_comment']


@server.tool()
@handle_http_errors("duplicate_sheet", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def duplicate_sheet(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    sheet_id: int,
    new_sheet_name: Optional[str] = None,
    insert_index: Optional[int] = None,
) -> str:
    """
    Duplicates a sheet. Returns new sheetId.
    """
    logger.info(f"[duplicate_sheet] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, SheetId={sheet_id}")

    dup_req: Dict[str, Any] = {
        "duplicateSheet": {
            "sourceSheetId": sheet_id,
        }
    }
    if new_sheet_name is not None:
        dup_req["duplicateSheet"]["newSheetName"] = new_sheet_name
    if insert_index is not None:
        dup_req["duplicateSheet"]["insertSheetIndex"] = insert_index

    result = await asyncio.to_thread(
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id, body={"requests": [dup_req]}
        ).execute
    )
    new_id = result.get("replies", [{}])[0].get("duplicateSheet", {}).get("properties", {}).get("sheetId")
    return f"Duplicated sheet {sheet_id} to new sheetId {new_id}."


@server.tool()
@handle_http_errors("delete_sheet", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def delete_sheet(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    sheet_id: int,
) -> str:
    """Deletes a sheet by sheetId."""
    logger.info(f"[delete_sheet] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, SheetId={sheet_id}")

    requests = [{"deleteSheet": {"sheetId": sheet_id}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return f"Deleted sheet {sheet_id}."


@server.tool()
@handle_http_errors("move_sheet", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def move_sheet(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    sheet_id: int,
    new_index: int,
) -> str:
    """Moves a sheet to a new tab index."""
    logger.info(f"[move_sheet] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, SheetId={sheet_id}, NewIndex={new_index}")

    requests = [
        {
            "updateSheetProperties": {
                "properties": {"sheetId": sheet_id, "index": new_index},
                "fields": "index",
            }
        }
    ]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return f"Moved sheet {sheet_id} to index {new_index}."


@server.tool()
@handle_http_errors("add_protected_range", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def add_protected_range(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    description: str,
    grid_range: Dict[str, Any],
    editors_emails: Optional[List[str]] = None,
    domain_users_can_edit: bool = False,
) -> str:
    """
    Adds a protected range. Returns protectedRangeId.
    """
    logger.info(f"[add_protected_range] Email='{user_google_email}', Spreadsheet={spreadsheet_id}")

    protection: Dict[str, Any] = {
        "range": grid_range,
        "description": description,
        "warningOnly": False,
        "editors": {
            "users": editors_emails or [],
            "domainUsersCanEdit": domain_users_can_edit,
        },
    }
    requests = [{"addProtectedRange": {"protectedRange": protection}}]
    result = await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    pr_id = result.get("replies", [{}])[0].get("addProtectedRange", {}).get("protectedRange", {}).get("protectedRangeId")
    return f"Added protected range with id {pr_id}."


@server.tool()
@handle_http_errors("delete_protected_range", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def delete_protected_range(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    protected_range_id: int,
) -> str:
    """Deletes a protected range by id."""
    logger.info(f"[delete_protected_range] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, ProtectedRangeId={protected_range_id}")

    requests = [{"deleteProtectedRange": {"protectedRangeId": protected_range_id}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return f"Deleted protected range {protected_range_id}."


@server.tool()
@handle_http_errors("create_filter_view", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def create_filter_view(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    title: str,
    grid_range: Dict[str, Any],
    criteria: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Creates a filter view over a range. Returns filterViewId.
    """
    logger.info(f"[create_filter_view] Email='{user_google_email}', Spreadsheet={spreadsheet_id}")

    filter_view: Dict[str, Any] = {
        "title": title,
        "range": grid_range,
    }
    if criteria:
        filter_view["criteria"] = criteria

    requests = [{"addFilterView": {"filter": filter_view}}]
    result = await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    fv_id = result.get("replies", [{}])[0].get("addFilterView", {}).get("filter", {}).get("filterViewId")
    return f"Created filter view '{title}' with id {fv_id}."


@server.tool()
@handle_http_errors("delete_filter_view", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def delete_filter_view(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    filter_view_id: int,
) -> str:
    """Deletes a filter view by id."""
    logger.info(f"[delete_filter_view] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, FilterViewId={filter_view_id}")

    requests = [{"deleteFilterView": {"filterId": filter_view_id}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return f"Deleted filter view {filter_view_id}."


@server.tool()
@handle_http_errors("add_chart", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def add_chart(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    chart_spec: Dict[str, Any],
    position: Dict[str, Any],
) -> str:
    """
    Adds a chart. Provide chart_spec (EmbeddedChart) and position (EmbeddedObjectPosition).
    Returns chart id.
    """
    logger.info(f"[add_chart] Email='{user_google_email}', Spreadsheet={spreadsheet_id}")

    requests = [{"addChart": {"chart": {**chart_spec, "position": position}}}]
    result = await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    chart_id = result.get("replies", [{}])[0].get("addChart", {}).get("chart", {}).get("chartId")
    return f"Added chart with id {chart_id}."


@server.tool()
@handle_http_errors("find_replace", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def find_replace(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    find: str,
    replacement: str,
    sheet_id: Optional[int] = None,
    range: Optional[Dict[str, Any]] = None,
    all_sheets: bool = False,
    search_by_regex: bool = False,
    match_case: bool = False,
    include_formulas: bool = False,
) -> str:
    """
    Performs find/replace across a range, sheet, or all sheets.
    """
    logger.info(f"[find_replace] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, Find='{find}'")

    fr: Dict[str, Any] = {
        "find": find,
        "replacement": replacement,
        "matchCase": match_case,
        "searchByRegex": search_by_regex,
        "includeFormulas": include_formulas,
    }
    if all_sheets:
        fr["allSheets"] = True
    if sheet_id is not None:
        fr["sheetId"] = sheet_id
    if range is not None:
        fr["range"] = range

    requests = [{"findReplace": fr}]
    result = await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    changes = result.get("replies", [{}])[0].get("findReplace", {}).get("occurrencesChanged", 0)
    return f"Replaced {changes} occurrence(s)."


@server.tool()
@handle_http_errors("copy_paste", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def copy_paste(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    source: Dict[str, Any],
    destination: Dict[str, Any],
    paste_type: str = "PASTE_NORMAL",
    paste_orientation: str = "NORMAL",
) -> str:
    """Copies from source GridRange to destination GridRange with options."""
    logger.info(f"[copy_paste] Email='{user_google_email}', Spreadsheet={spreadsheet_id}")

    requests = [
        {
            "copyPaste": {
                "source": source,
                "destination": destination,
                "pasteType": paste_type,
                "pasteOrientation": paste_orientation,
            }
        }
    ]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return "Copy/paste completed."


@server.tool()
@handle_http_errors("create_pivot_table", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def create_pivot_table(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    source: Dict[str, Any],
    anchor_cell: Dict[str, int],
    rows: Optional[List[Dict[str, Any]]] = None,
    columns: Optional[List[Dict[str, Any]]] = None,
    values: Optional[List[Dict[str, Any]]] = None,
    criteria: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Creates a pivot table at anchor_cell (sheetId,rowIndex,columnIndex) using source GridRange.
    """
    logger.info(f"[create_pivot_table] Email='{user_google_email}', Spreadsheet={spreadsheet_id}")

    pivot: Dict[str, Any] = {"source": source}
    if rows:
        pivot["rows"] = rows
    if columns:
        pivot["columns"] = columns
    if values:
        pivot["values"] = values
    if criteria:
        pivot["criteria"] = criteria

    requests = [
        {
            "addPivotTable": {
                "pivotTable": pivot,
                "anchorCell": anchor_cell,
            }
        }
    ]

    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return "Created pivot table."


@server.tool()
@handle_http_errors("update_borders", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def update_borders(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    grid_range: Dict[str, Any],
    top: Optional[Dict[str, Any]] = None,
    bottom: Optional[Dict[str, Any]] = None,
    left: Optional[Dict[str, Any]] = None,
    right: Optional[Dict[str, Any]] = None,
    inner_horizontal: Optional[Dict[str, Any]] = None,
    inner_vertical: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Updates borders for a GridRange. Each border dict matches Sheets API Border schema.
    Provide any subset of: top, bottom, left, right, inner_horizontal, inner_vertical.
    """
    logger.info(f"[update_borders] Email='{user_google_email}', Spreadsheet={spreadsheet_id}")

    borders: Dict[str, Any] = {"range": grid_range}
    if top is not None:
        borders["top"] = top
    if bottom is not None:
        borders["bottom"] = bottom
    if left is not None:
        borders["left"] = left
    if right is not None:
        borders["right"] = right
    if inner_horizontal is not None:
        borders["innerHorizontal"] = inner_horizontal
    if inner_vertical is not None:
        borders["innerVertical"] = inner_vertical

    requests = [{"updateBorders": borders}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return "Updated borders for range."


@server.tool()
@handle_http_errors("add_developer_metadata", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def add_developer_metadata(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    metadata: Dict[str, Any],
) -> str:
    """
    Creates developer metadata. 'metadata' should match DeveloperMetadata schema (location, key, value, visibility).
    Returns created metadataId.
    """
    logger.info(f"[add_developer_metadata] Email='{user_google_email}', Spreadsheet={spreadsheet_id}")
    requests = [{"createDeveloperMetadata": {"developerMetadata": metadata}}]
    result = await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    md_id = result.get("replies", [{}])[0].get("createDeveloperMetadata", {}).get("developerMetadata", {}).get("metadataId")
    return f"Created developer metadata with id {md_id}."


@server.tool()
@handle_http_errors("update_developer_metadata_by_id", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def update_developer_metadata_by_id(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    metadata_id: int,
    developer_metadata: Dict[str, Any],
    fields: str,
) -> str:
    """
    Updates developer metadata by ID. Provide fields mask (e.g., "metadataKey,metadataValue,visibility").
    """
    logger.info(f"[update_developer_metadata_by_id] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, MetadataId={metadata_id}")
    req = {
        "updateDeveloperMetadata": {
            "dataFilters": [{"developerMetadataLookup": {"metadataId": metadata_id}}],
            "developerMetadata": developer_metadata,
            "fields": fields,
        }
    }
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": [req]}).execute
    )
    return f"Updated developer metadata {metadata_id}."


@server.tool()
@handle_http_errors("delete_developer_metadata_by_id", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def delete_developer_metadata_by_id(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    metadata_id: int,
) -> str:
    """Deletes developer metadata by ID."""
    logger.info(f"[delete_developer_metadata_by_id] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, MetadataId={metadata_id}")
    req = {
        "deleteDeveloperMetadata": {
            "dataFilter": {"developerMetadataLookup": {"metadataId": metadata_id}}
        }
    }
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": [req]}).execute
    )
    return f"Deleted developer metadata {metadata_id}."


@server.tool()
@handle_http_errors("add_dimension_group", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def add_dimension_group(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    sheet_id: int,
    dimension: str,
    start_index: int,
    end_index: int,
) -> str:
    """Adds a dimension group for a row/column span."""
    logger.info(f"[add_dimension_group] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, SheetId={sheet_id}")
    dim_range = {"sheetId": sheet_id, "dimension": dimension, "startIndex": start_index, "endIndex": end_index}
    requests = [{"addDimensionGroup": {"range": dim_range}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return f"Added {dimension.lower()} group {start_index}:{end_index} on sheet {sheet_id}."


@server.tool()
@handle_http_errors("delete_dimension_group", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def delete_dimension_group(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    sheet_id: int,
    dimension: str,
    start_index: int,
    end_index: int,
) -> str:
    """Deletes a dimension group for a row/column span."""
    logger.info(f"[delete_dimension_group] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, SheetId={sheet_id}")
    dim_range = {"sheetId": sheet_id, "dimension": dimension, "startIndex": start_index, "endIndex": end_index}
    requests = [{"deleteDimensionGroup": {"range": dim_range}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return f"Deleted {dimension.lower()} group {start_index}:{end_index} on sheet {sheet_id}."


@server.tool()
@handle_http_errors("set_dimension_group_collapse", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def set_dimension_group_collapse(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    sheet_id: int,
    dimension: str,
    start_index: int,
    end_index: int,
    collapsed: bool,
) -> str:
    """
    Collapses or expands a dimension group using updateDimensionGroup.
    """
    logger.info(f"[set_dimension_group_collapse] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, SheetId={sheet_id}")
    dim_group = {
        "range": {"sheetId": sheet_id, "dimension": dimension, "startIndex": start_index, "endIndex": end_index},
        "collapsed": collapsed,
    }
    requests = [{"updateDimensionGroup": {"dimensionGroup": dim_group, "fields": "collapsed"}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return ("Collapsed" if collapsed else "Expanded") + f" {dimension.lower()} group {start_index}:{end_index} on sheet {sheet_id}."


@server.tool()
@handle_http_errors("update_conditional_format_rule", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def update_conditional_format_rule(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    sheet_id: int,
    index: int,
    rule: Dict[str, Any],
) -> str:
    """Updates an existing conditional format rule at sheet/index."""
    logger.info(f"[update_conditional_format_rule] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, SheetId={sheet_id}, Index={index}")
    requests = [{"updateConditionalFormatRule": {"index": index, "sheetId": sheet_id, "rule": rule}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return f"Updated conditional format rule at index {index} on sheetId {sheet_id}."


@server.tool()
@handle_http_errors("import_csv_to_sheet", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def import_csv_to_sheet(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    sheet_title: str,
    csv_text: str,
    clear_before: bool = True,
    delimiter: str = ",",
) -> str:
    """
    Imports CSV/TSV data into a sheet starting at A1 by parsing the given csv_text and writing values.
    Args:
        sheet_title: Target sheet title (tab name).
        csv_text: Raw CSV text (UTF-8). Large data may need chunking client-side.
        delimiter: Default ','; set to '\t' for TSV.
    """
    import csv
    from io import StringIO

    logger.info(f"[import_csv_to_sheet] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, Sheet='{sheet_title}', Clear={clear_before}")

    reader = csv.reader(StringIO(csv_text), delimiter=delimiter)
    values: List[List[str]] = [list(row) for row in reader]

    range_name = f"{sheet_title}!A1"

    if clear_before:
        await asyncio.to_thread(
            service.spreadsheets().values().clear(spreadsheetId=spreadsheet_id, range=f"{sheet_title}").execute
        )

    if not values:
        return f"No rows to import into '{sheet_title}'."

    body = {"valueInputOption": "USER_ENTERED", "data": [{"range": range_name, "values": values}]}
    result = await asyncio.to_thread(
        service.spreadsheets().values().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute
    )
    total_cells = result.get("totalUpdatedCells", 0)
    return f"Imported {len(values)} row(s) into '{sheet_title}'. Updated {total_cells} cell(s)."


@server.tool()
@handle_http_errors("insert_dimension", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def insert_dimension(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    sheet_id: int,
    dimension: str,
    start_index: int,
    end_index: int,
    inherit_from_before: bool = False,
) -> str:
    """Inserts rows/columns in a given index span."""
    logger.info(f"[insert_dimension] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, SheetId={sheet_id}")
    requests = [{
        "insertDimension": {
            "range": {"sheetId": sheet_id, "dimension": dimension, "startIndex": start_index, "endIndex": end_index},
            "inheritFromBefore": inherit_from_before,
        }
    }]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return f"Inserted {dimension.lower()} {start_index}:{end_index} on sheet {sheet_id}."


@server.tool()
@handle_http_errors("delete_dimension", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def delete_dimension(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    sheet_id: int,
    dimension: str,
    start_index: int,
    end_index: int,
) -> str:
    """Deletes rows/columns in a given index span."""
    logger.info(f"[delete_dimension] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, SheetId={sheet_id}")
    requests = [{
        "deleteDimension": {
            "range": {"sheetId": sheet_id, "dimension": dimension, "startIndex": start_index, "endIndex": end_index}
        }
    }]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return f"Deleted {dimension.lower()} {start_index}:{end_index} on sheet {sheet_id}."


@server.tool()
@handle_http_errors("move_dimension", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def move_dimension(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    sheet_id: int,
    dimension: str,
    start_index: int,
    end_index: int,
    destination_index: int,
) -> str:
    """Moves a row/column span to a new index."""
    logger.info(f"[move_dimension] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, SheetId={sheet_id}")
    requests = [{
        "moveDimension": {
            "source": {"sheetId": sheet_id, "dimension": dimension, "startIndex": start_index, "endIndex": end_index},
            "destinationIndex": destination_index,
        }
    }]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return f"Moved {dimension.lower()} {start_index}:{end_index} to index {destination_index} on sheet {sheet_id}."


@server.tool()
@handle_http_errors("set_basic_filter", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def set_basic_filter(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    filter_spec: Dict[str, Any],
) -> str:
    """Sets a basic filter on a sheet/range (SetBasicFilter)."""
    logger.info(f"[set_basic_filter] Email='{user_google_email}', Spreadsheet={spreadsheet_id}")
    requests = [{"setBasicFilter": {"filter": filter_spec}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return "Applied basic filter."


@server.tool()
@handle_http_errors("clear_basic_filter", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def clear_basic_filter(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    sheet_id: int,
) -> str:
    """Clears the basic filter from a sheet (ClearBasicFilter)."""
    logger.info(f"[clear_basic_filter] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, SheetId={sheet_id}")
    requests = [{"clearBasicFilter": {"sheetId": sheet_id}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return f"Cleared basic filter on sheet {sheet_id}."


@server.tool()
@handle_http_errors("add_banding", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def add_banding(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    banded_range: Dict[str, Any],
) -> str:
    """Adds a banded range (alternating row/column colors)."""
    logger.info(f"[add_banding] Email='{user_google_email}', Spreadsheet={spreadsheet_id}")
    requests = [{"addBanding": {"bandedRange": banded_range}}]
    result = await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    br_id = result.get("replies", [{}])[0].get("addBanding", {}).get("bandedRange", {}).get("bandedRangeId")
    return f"Added banding with id {br_id}."


@server.tool()
@handle_http_errors("update_banding", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def update_banding(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    banded_range: Dict[str, Any],
    fields: str,
) -> str:
    """Updates an existing banded range (colors/range/etc.)."""
    logger.info(f"[update_banding] Email='{user_google_email}', Spreadsheet={spreadsheet_id}")
    requests = [{"updateBanding": {"bandedRange": banded_range, "fields": fields}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return "Updated banding."


@server.tool()
@handle_http_errors("delete_banding", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def delete_banding(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    banded_range_id: int,
) -> str:
    """Deletes a banded range by id."""
    logger.info(f"[delete_banding] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, BandedRangeId={banded_range_id}")
    requests = [{"deleteBanding": {"bandedRangeId": banded_range_id}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return f"Deleted banding {banded_range_id}."


@server.tool()
@handle_http_errors("update_named_range", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def update_named_range(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    named_range: Dict[str, Any],
    fields: str,
) -> str:
    """Updates a named range with fields mask."""
    logger.info(f"[update_named_range] Email='{user_google_email}', Spreadsheet={spreadsheet_id}")
    requests = [{"updateNamedRange": {"namedRange": named_range, "fields": fields}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return "Updated named range."


@server.tool()
@handle_http_errors("update_protected_range", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def update_protected_range(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    protected_range: Dict[str, Any],
    fields: str,
) -> str:
    """Updates a protected range with fields mask."""
    logger.info(f"[update_protected_range] Email='{user_google_email}', Spreadsheet={spreadsheet_id}")
    requests = [{"updateProtectedRange": {"protectedRange": protected_range, "fields": fields}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return "Updated protected range."


@server.tool()
@handle_http_errors("update_filter_view", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def update_filter_view(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    filter_view: Dict[str, Any],
    fields: str,
) -> str:
    """Updates a filter view with fields mask."""
    logger.info(f"[update_filter_view] Email='{user_google_email}', Spreadsheet={spreadsheet_id}")
    requests = [{"updateFilterView": {"filter": filter_view, "fields": fields}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return "Updated filter view."


@server.tool()
@handle_http_errors("update_chart_spec", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def update_chart_spec(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    chart_id: int,
    spec: Dict[str, Any],
) -> str:
    """Updates the spec of an existing chart (UpdateChartSpec)."""
    logger.info(f"[update_chart_spec] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, ChartId={chart_id}")
    requests = [{"updateChartSpec": {"chartId": chart_id, "spec": spec}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return f"Updated chart {chart_id}."


@server.tool()
@handle_http_errors("delete_embedded_object", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def delete_embedded_object(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    object_id: int,
) -> str:
    """Deletes an embedded object (chart/slicer/etc.) by object id."""
    logger.info(f"[delete_embedded_object] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, ObjectId={object_id}")
    requests = [{"deleteEmbeddedObject": {"objectId": object_id}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return f"Deleted embedded object {object_id}."


@server.tool()
@handle_http_errors("set_spreadsheet_properties", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def set_spreadsheet_properties(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    properties: Dict[str, Any],
    fields: str,
) -> str:
    """Updates spreadsheet-level properties (locale, timeZone, defaultFormat, title, etc.)."""
    logger.info(f"[set_spreadsheet_properties] Email='{user_google_email}', Spreadsheet={spreadsheet_id}")
    requests = [{"updateSpreadsheetProperties": {"properties": properties, "fields": fields}}]
    await asyncio.to_thread(
        service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body={"requests": requests}).execute
    )
    return "Updated spreadsheet properties."


@server.tool()
@handle_http_errors("batch_get_values_by_data_filter", is_read_only=True, service_type="sheets")
@require_google_service("sheets", "sheets_read")
async def batch_get_values_by_data_filter(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    data_filters: List[Dict[str, Any]],
    major_dimension: Optional[str] = None,
) -> str:
    """Reads values using DataFilters (range/sheet metadata queries)."""
    logger.info(f"[batch_get_values_by_data_filter] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, Filters={len(data_filters)}")
    body: Dict[str, Any] = {"dataFilters": data_filters}
    if major_dimension:
        body["majorDimension"] = major_dimension
    result = await asyncio.to_thread(
        service.spreadsheets().values().batchGetByDataFilter(spreadsheetId=spreadsheet_id, body=body).execute
    )
    value_ranges = result.get("valueRanges", [])
    return f"Retrieved {len(value_ranges)} data-filtered range(s)."


@server.tool()
@handle_http_errors("batch_update_values_by_data_filter", service_type="sheets")
@require_google_service("sheets", "sheets_write")
async def batch_update_values_by_data_filter(
    service,
    user_google_email: str,
    spreadsheet_id: str,
    data: List[Dict[str, Any]],
    value_input_option: str = "USER_ENTERED",
) -> str:
    """Updates values using DataFilters. Data items contain {dataFilter, values}."""
    logger.info(f"[batch_update_values_by_data_filter] Email='{user_google_email}', Spreadsheet={spreadsheet_id}, Items={len(data)}")
    body = {"valueInputOption": value_input_option, "data": data}
    result = await asyncio.to_thread(
        service.spreadsheets().values().batchUpdateByDataFilter(spreadsheetId=spreadsheet_id, body=body).execute
    )
    total_cells = result.get("totalUpdatedCells", 0)
    total_rows = result.get("totalUpdatedRows", 0)
    return f"Updated {total_rows} row(s) and {total_cells} cell(s) via data filters."
