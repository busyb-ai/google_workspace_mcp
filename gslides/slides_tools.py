"""
Google Slides MCP Tools

This module provides MCP tools for interacting with Google Slides API.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional


from auth.service_decorator import require_google_service
from core.server import server
from core.utils import handle_http_errors
from core.comments import create_comment_tools

logger = logging.getLogger(__name__)


@server.tool()
@handle_http_errors("create_presentation", service_type="slides")
@require_google_service("slides", "slides")
async def create_presentation(
    service,
    user_google_email: str, user_id: Optional[str] = None,
    title: str = "Untitled Presentation"
) -> str:
    """
    Create a new Google Slides presentation.

    Args:
        user_google_email (str): The user's Google email address. Required.
        title (str): The title for the new presentation. Defaults to "Untitled Presentation".

    Returns:
        str: Details about the created presentation including ID and URL.
    """
    logger.info(f"[create_presentation] Invoked. Email: '{user_google_email}', Title: '{title}'")

    body = {
        'title': title
    }

    result = await asyncio.to_thread(
        service.presentations().create(body=body).execute
    )

    presentation_id = result.get('presentationId')
    presentation_url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"

    confirmation_message = f"""Presentation Created Successfully for {user_google_email}:
- Title: {title}
- Presentation ID: {presentation_id}
- URL: {presentation_url}
- Slides: {len(result.get('slides', []))} slide(s) created"""

    logger.info(f"Presentation created successfully for {user_google_email}")
    return confirmation_message


@server.tool()
@handle_http_errors("get_presentation", is_read_only=True, service_type="slides")
@require_google_service("slides", "slides_read")
async def get_presentation(
    service,
    user_google_email: str,
    presentation_id: str,
    user_id: Optional[str] = None,
) -> str:
    """
    Get details about a Google Slides presentation.

    Args:
        user_google_email (str): The user's Google email address. Required.
        presentation_id (str): The ID of the presentation to retrieve.

    Returns:
        str: Details about the presentation including title, slides count, and metadata.
    """
    logger.info(f"[get_presentation] Invoked. Email: '{user_google_email}', ID: '{presentation_id}'")

    result = await asyncio.to_thread(
        service.presentations().get(presentationId=presentation_id).execute
    )

    title = result.get('title', 'Untitled')
    slides = result.get('slides', [])
    page_size = result.get('pageSize', {})

    slides_info = []
    for i, slide in enumerate(slides, 1):
        slide_id = slide.get('objectId', 'Unknown')
        page_elements = slide.get('pageElements', [])
        slides_info.append(f"  Slide {i}: ID {slide_id}, {len(page_elements)} element(s)")

    confirmation_message = f"""Presentation Details for {user_google_email}:
- Title: {title}
- Presentation ID: {presentation_id}
- URL: https://docs.google.com/presentation/d/{presentation_id}/edit
- Total Slides: {len(slides)}
- Page Size: {page_size.get('width', {}).get('magnitude', 'Unknown')} x {page_size.get('height', {}).get('magnitude', 'Unknown')} {page_size.get('width', {}).get('unit', '')}

Slides Breakdown:
{chr(10).join(slides_info) if slides_info else '  No slides found'}"""

    logger.info(f"Presentation retrieved successfully for {user_google_email}")
    return confirmation_message


@server.tool()
@handle_http_errors("batch_update_presentation", service_type="slides")
@require_google_service("slides", "slides")
async def batch_update_presentation(
    service,
    user_google_email: str,
    presentation_id: str,
    requests: List[Dict[str, Any]],
    user_id: Optional[str] = None,
) -> str:
    """
    Apply batch updates to a Google Slides presentation.

    Args:
        user_google_email (str): The user's Google email address. Required.
        presentation_id (str): The ID of the presentation to update.
        requests (List[Dict[str, Any]]): List of update requests to apply.

    Returns:
        str: Details about the batch update operation results.
    """
    logger.info(f"[batch_update_presentation] Invoked. Email: '{user_google_email}', ID: '{presentation_id}', Requests: {len(requests)}")

    body = {
        'requests': requests
    }

    result = await asyncio.to_thread(
        service.presentations().batchUpdate(
            presentationId=presentation_id,
            body=body
        ).execute
    )

    replies = result.get('replies', [])

    confirmation_message = f"""Batch Update Completed for {user_google_email}:
- Presentation ID: {presentation_id}
- URL: https://docs.google.com/presentation/d/{presentation_id}/edit
- Requests Applied: {len(requests)}
- Replies Received: {len(replies)}"""

    if replies:
        confirmation_message += "\n\nUpdate Results:"
        for i, reply in enumerate(replies, 1):
            if 'createSlide' in reply:
                slide_id = reply['createSlide'].get('objectId', 'Unknown')
                confirmation_message += f"\n  Request {i}: Created slide with ID {slide_id}"
            elif 'createShape' in reply:
                shape_id = reply['createShape'].get('objectId', 'Unknown')
                confirmation_message += f"\n  Request {i}: Created shape with ID {shape_id}"
            else:
                confirmation_message += f"\n  Request {i}: Operation completed"

    logger.info(f"Batch update completed successfully for {user_google_email}")
    return confirmation_message


@server.tool()
@handle_http_errors("get_page", is_read_only=True, service_type="slides")
@require_google_service("slides", "slides_read")
async def get_page(
    service,
    user_google_email: str,
    presentation_id: str,
    page_object_id: str,
    user_id: Optional[str] = None,
) -> str:
    """
    Get details about a specific page (slide) in a presentation.

    Args:
        user_google_email (str): The user's Google email address. Required.
        presentation_id (str): The ID of the presentation.
        page_object_id (str): The object ID of the page/slide to retrieve.

    Returns:
        str: Details about the specific page including elements and layout.
    """
    logger.info(f"[get_page] Invoked. Email: '{user_google_email}', Presentation: '{presentation_id}', Page: '{page_object_id}'")

    result = await asyncio.to_thread(
        service.presentations().pages().get(
            presentationId=presentation_id,
            pageObjectId=page_object_id
        ).execute
    )

    page_type = result.get('pageType', 'Unknown')
    page_elements = result.get('pageElements', [])

    elements_info = []
    for element in page_elements:
        element_id = element.get('objectId', 'Unknown')
        if 'shape' in element:
            shape_type = element['shape'].get('shapeType', 'Unknown')
            elements_info.append(f"  Shape: ID {element_id}, Type: {shape_type}")
        elif 'table' in element:
            table = element['table']
            rows = table.get('rows', 0)
            cols = table.get('columns', 0)
            elements_info.append(f"  Table: ID {element_id}, Size: {rows}x{cols}")
        elif 'line' in element:
            line_type = element['line'].get('lineType', 'Unknown')
            elements_info.append(f"  Line: ID {element_id}, Type: {line_type}")
        else:
            elements_info.append(f"  Element: ID {element_id}, Type: Unknown")

    confirmation_message = f"""Page Details for {user_google_email}:
- Presentation ID: {presentation_id}
- Page ID: {page_object_id}
- Page Type: {page_type}
- Total Elements: {len(page_elements)}

Page Elements:
{chr(10).join(elements_info) if elements_info else '  No elements found'}"""

    logger.info(f"Page retrieved successfully for {user_google_email}")
    return confirmation_message


@server.tool()
@handle_http_errors("get_page_thumbnail", is_read_only=True, service_type="slides")
@require_google_service("slides", "slides_read")
async def get_page_thumbnail(
    service,
    user_google_email: str, presentation_id: str,
    page_object_id: str,
    thumbnail_size: str = "MEDIUM",
    user_id: Optional[str] = None
) -> str:
    """
    Generate a thumbnail URL for a specific page (slide) in a presentation.

    Args:
        user_google_email (str): The user's Google email address. Required.
        presentation_id (str): The ID of the presentation.
        page_object_id (str): The object ID of the page/slide.
        thumbnail_size (str): Size of thumbnail ("LARGE", "MEDIUM", "SMALL"). Defaults to "MEDIUM".

    Returns:
        str: URL to the generated thumbnail image.
    """
    logger.info(f"[get_page_thumbnail] Invoked. Email: '{user_google_email}', Presentation: '{presentation_id}', Page: '{page_object_id}', Size: '{thumbnail_size}'")

    result = await asyncio.to_thread(
        service.presentations().pages().getThumbnail(
            presentationId=presentation_id,
            pageObjectId=page_object_id,
            thumbnailProperties_thumbnailSize=thumbnail_size,
            thumbnailProperties_mimeType='PNG'
        ).execute
    )

    thumbnail_url = result.get('contentUrl', '')

    confirmation_message = f"""Thumbnail Generated for {user_google_email}:
- Presentation ID: {presentation_id}
- Page ID: {page_object_id}
- Thumbnail Size: {thumbnail_size}
- Thumbnail URL: {thumbnail_url}

You can view or download the thumbnail using the provided URL."""

    logger.info(f"Thumbnail generated successfully for {user_google_email}")
    return confirmation_message


@server.tool()
@handle_http_errors("create_slide", service_type="slides")
@require_google_service("slides", "slides")
async def create_slide(
    service,
    user_google_email: str, presentation_id: str,user_id: Optional[str] = None,
    
    predefined_layout: Optional[str] = "TITLE_AND_BODY",
    insertion_index: Optional[int] = None,
    object_id: Optional[str] = None,
) -> str:
    """
    Create a new slide with an optional predefined layout and insertion index.
    """
    logger.info(f"[create_slide] Email='{user_google_email}', Presentation={presentation_id}, Layout={predefined_layout}")

    req: Dict[str, Any] = {
        "createSlide": {
            "slideLayoutReference": {"predefinedLayout": predefined_layout} if predefined_layout else {},
        }
    }
    if insertion_index is not None:
        req["createSlide"]["insertionIndex"] = insertion_index
    if object_id:
        req["createSlide"]["objectId"] = object_id

    result = await asyncio.to_thread(
        service.presentations().batchUpdate(
            presentationId=presentation_id, body={"requests": [req]}
        ).execute
    )
    new_id = result.get("replies", [{}])[0].get("createSlide", {}).get("objectId")
    return f"Created slide with id {new_id}."


@server.tool()
@handle_http_errors("duplicate_object", service_type="slides")
@require_google_service("slides", "slides")
async def duplicate_object(
    service,
    user_google_email: str, presentation_id: str,
    object_id: str,
    object_ids: Optional[Dict[str, str]] = None,
    user_id: Optional[str] = None,
) -> str:
    """Duplicate a slide or page element. Optionally provide objectIds mapping."""
    logger.info(f"[duplicate_object] Email='{user_google_email}', Presentation={presentation_id}, Object={object_id}")
    req = {"duplicateObject": {"objectId": object_id}}
    if object_ids:
        req["duplicateObject"]["objectIds"] = object_ids

    result = await asyncio.to_thread(
        service.presentations().batchUpdate(
            presentationId=presentation_id, body={"requests": [req]}
        ).execute
    )
    new_id = result.get("replies", [{}])[0].get("duplicateObject", {}).get("objectId")
    return f"Duplicated object {object_id} to {new_id}."


@server.tool()
@handle_http_errors("delete_object", service_type="slides")
@require_google_service("slides", "slides")
async def delete_object(
    service,
    user_google_email: str, presentation_id: str,
    object_id: str,
    user_id: Optional[str] = None
) -> str:
    """Delete a slide or page element by object id."""
    logger.info(f"[delete_object] Email='{user_google_email}', Presentation={presentation_id}, Object={object_id}")
    req = {"deleteObject": {"objectId": object_id}}
    await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    return f"Deleted object {object_id}."


@server.tool()
@handle_http_errors("move_slides", service_type="slides")
@require_google_service("slides", "slides")
async def move_slides(
    service,
    user_google_email: str, presentation_id: str,
    slide_object_ids: List[str],
    insertion_index: int,
    user_id: Optional[str] = None,
) -> str:
    """Reorder slides by moving the given slide ids to the insertion index."""
    logger.info(f"[move_slides] Email='{user_google_email}', Presentation={presentation_id}, Count={len(slide_object_ids)}")
    req = {
        "updateSlidesPosition": {
            "slideObjectIds": slide_object_ids,
            "insertionIndex": insertion_index,
        }
    }
    await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    return f"Moved {len(slide_object_ids)} slide(s) to index {insertion_index}."


@server.tool()
@handle_http_errors("create_shape", service_type="slides")
@require_google_service("slides", "slides")
async def create_shape(
    service,
    user_google_email: str, presentation_id: str,
    shape_type: str,
    element_properties: Dict[str, Any],
    user_id: Optional[str] = None,
    object_id: Optional[str] = None,
) -> str:
    """Create a shape on a slide. element_properties must include pageObjectId and transform/size."""
    logger.info(f"[create_shape] Email='{user_google_email}', Presentation={presentation_id}, Type={shape_type}")
    req: Dict[str, Any] = {
        "createShape": {
            "shapeType": shape_type,
            "elementProperties": element_properties,
        }
    }
    if object_id:
        req["createShape"]["objectId"] = object_id

    result = await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    new_id = result.get("replies", [{}])[0].get("createShape", {}).get("objectId")
    return f"Created shape with id {new_id}."


@server.tool()
@handle_http_errors("insert_text", service_type="slides")
@require_google_service("slides", "slides")
async def insert_text(
    service,
    user_google_email: str, presentation_id: str,
    object_id: str,
    text: str,
    user_id: Optional[str] = None,
    insertion_index: int = 0,
) -> str:
    """Insert text into a shape or table cell-containing object at a given index."""
    logger.info(f"[insert_text] Email='{user_google_email}', Presentation={presentation_id}, Object={object_id}")
    req = {"insertText": {"objectId": object_id, "text": text, "insertionIndex": insertion_index}}
    await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    return f"Inserted text into {object_id}."


@server.tool()
@handle_http_errors("replace_all_text", service_type="slides")
@require_google_service("slides", "slides")
async def replace_all_text(
    service,
    user_google_email: str, presentation_id: str,
    contains_text: Dict[str, Any],
    replace_text: str,
    page_object_ids: Optional[List[str]] = None,
    case_sensitive: bool = False,
) -> str:
    """Replace all matches of contains_text with replace_text, optionally limited to specific pages."""
    logger.info(f"[replace_all_text] Email='{user_google_email}', Presentation={presentation_id}")
    req: Dict[str, Any] = {
        "replaceAllText": {
            "containsText": contains_text,
            "replaceText": replace_text,
            "caseSensitive": case_sensitive,
        }
    }
    if page_object_ids:
        req["replaceAllText"]["pageObjectIds"] = page_object_ids

    result = await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    changed = result.get("replies", [{}])[0].get("replaceAllText", {}).get("occurrencesChanged", 0)
    return f"Replaced {changed} occurrence(s)."


@server.tool()
@handle_http_errors("update_text_style", service_type="slides")
@require_google_service("slides", "slides")
async def update_text_style(
    service,
    user_google_email: str, presentation_id: str,
    object_id: str,
    text_range: Dict[str, Any],
    style: Dict[str, Any],
    fields: str,
) -> str:
    """Update text style for a given object and range."""
    logger.info(f"[update_text_style] Email='{user_google_email}', Presentation={presentation_id}, Object={object_id}")
    req = {
        "updateTextStyle": {
            "objectId": object_id,
            "textRange": text_range,
            "style": style,
            "fields": fields,
        }
    }
    await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    return "Updated text style."


@server.tool()
@handle_http_errors("update_paragraph_style", service_type="slides")
@require_google_service("slides", "slides")
async def update_paragraph_style(
    service,
    user_google_email: str, presentation_id: str,
    object_id: str,
    text_range: Dict[str, Any],
    style: Dict[str, Any],
    fields: str,
) -> str:
    """Update paragraph style for a given object and range."""
    logger.info(f"[update_paragraph_style] Email='{user_google_email}', Presentation={presentation_id}, Object={object_id}")
    req = {
        "updateParagraphStyle": {
            "objectId": object_id,
            "textRange": text_range,
            "style": style,
            "fields": fields,
        }
    }
    await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    return "Updated paragraph style."


@server.tool()
@handle_http_errors("create_image", service_type="slides")
@require_google_service("slides", "slides")
async def create_image(
    service,
    user_google_email: str, presentation_id: str,
    image_url: str,
    element_properties: Dict[str, Any],
    object_id: Optional[str] = None,
) -> str:
    """Create an image from a public URL at a specific position/size on a slide."""
    logger.info(f"[create_image] Email='{user_google_email}', Presentation={presentation_id}")
    req: Dict[str, Any] = {
        "createImage": {
            "url": image_url,
            "elementProperties": element_properties,
        }
    }
    if object_id:
        req["createImage"]["objectId"] = object_id

    result = await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    new_id = result.get("replies", [{}])[0].get("createImage", {}).get("objectId")
    return f"Created image with id {new_id}."


@server.tool()
@handle_http_errors("replace_image", service_type="slides")
@require_google_service("slides", "slides")
async def replace_image(
    service,
    user_google_email: str, presentation_id: str,
    object_id: str,
    image_url: str,
    user_id: Optional[str] = None,
) -> str:
    """Replace the image content of an existing image object with a new URL."""
    logger.info(f"[replace_image] Email='{user_google_email}', Presentation={presentation_id}, Object={object_id}")
    req = {"replaceImage": {"imageObjectId": object_id, "url": image_url}}
    await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    return f"Replaced image for {object_id}."


@server.tool()
@handle_http_errors("create_table", service_type="slides")
@require_google_service("slides", "slides")
async def create_table(
    service,
    user_google_email: str, presentation_id: str,
    rows: int,
    columns: int,
    element_properties: Dict[str, Any],
    user_id: Optional[str] = None,
    object_id: Optional[str] = None,
) -> str:
    """Create a table on a slide with specified rows/columns and placement."""
    logger.info(f"[create_table] Email='{user_google_email}', Presentation={presentation_id}, Size={rows}x{columns}")
    req: Dict[str, Any] = {
        "createTable": {
            "rows": rows,
            "columns": columns,
            "elementProperties": element_properties,
        }
    }
    if object_id:
        req["createTable"]["objectId"] = object_id

    result = await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    new_id = result.get("replies", [{}])[0].get("createTable", {}).get("objectId")
    return f"Created table with id {new_id}."


@server.tool()
@handle_http_errors("update_table_cell_properties", service_type="slides")
@require_google_service("slides", "slides")
async def update_table_cell_properties(
    service,
    user_google_email: str, presentation_id: str,
    object_id: str,
    table_range: Dict[str, Any],
    table_cell_properties: Dict[str, Any],
    fields: str,
) -> str:
    """Update style properties for table cells within a given range for a table object."""
    logger.info(f"[update_table_cell_properties] Email='{user_google_email}', Presentation={presentation_id}, Object={object_id}")
    req = {
        "updateTableCellProperties": {
            "objectId": object_id,
            "tableRange": table_range,
            "tableCellProperties": table_cell_properties,
            "fields": fields,
        }
    }
    await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    return "Updated table cell properties."


@server.tool()
@handle_http_errors("merge_table_cells", service_type="slides")
@require_google_service("slides", "slides")
async def merge_table_cells(
    service,
    user_google_email: str, presentation_id: str,
    object_id: str,
    table_range: Dict[str, Any],
) -> str:
    """Merge table cells within the given range for a table object."""
    logger.info(f"[merge_table_cells] Email='{user_google_email}', Presentation={presentation_id}, Object={object_id}")
    req = {"mergeTableCells": {"objectId": object_id, "tableRange": table_range}}
    await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    return "Merged table cells."


@server.tool()
@handle_http_errors("unmerge_table_cells", service_type="slides")
@require_google_service("slides", "slides")
async def unmerge_table_cells(
    service,
    user_google_email: str, presentation_id: str,
    object_id: str,
    table_range: Dict[str, Any],
) -> str:
    """Unmerge table cells within the given range for a table object."""
    logger.info(f"[unmerge_table_cells] Email='{user_google_email}', Presentation={presentation_id}, Object={object_id}")
    req = {"unmergeTableCells": {"objectId": object_id, "tableRange": table_range}}
    await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    return "Unmerged table cells."


@server.tool()
@handle_http_errors("create_paragraph_bullets", service_type="slides")
@require_google_service("slides", "slides")
async def create_paragraph_bullets(
    service,
    user_google_email: str, presentation_id: str,
    object_id: str,
    text_range: Dict[str, Any],
    bullet_preset: Optional[str] = None,
) -> str:
    """Create bullets for the specified text range within an object."""
    logger.info(f"[create_paragraph_bullets] Email='{user_google_email}', Presentation={presentation_id}, Object={object_id}")
    req: Dict[str, Any] = {
        "createParagraphBullets": {
            "objectId": object_id,
            "textRange": text_range,
        }
    }
    if bullet_preset:
        req["createParagraphBullets"]["bulletPreset"] = bullet_preset

    await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    return "Created paragraph bullets."


@server.tool()
@handle_http_errors("delete_paragraph_bullets", service_type="slides")
@require_google_service("slides", "slides")
async def delete_paragraph_bullets(
    service,
    user_google_email: str, presentation_id: str,
    object_id: str,
    text_range: Dict[str, Any],
) -> str:
    """Delete bullets for the specified text range within an object."""
    logger.info(f"[delete_paragraph_bullets] Email='{user_google_email}', Presentation={presentation_id}, Object={object_id}")
    req = {"deleteParagraphBullets": {"objectId": object_id, "textRange": text_range}}
    await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    return "Deleted paragraph bullets."


@server.tool()
@handle_http_errors("update_page_properties", service_type="slides")
@require_google_service("slides", "slides")
async def update_page_properties(
    service,
    user_google_email: str, presentation_id: str,
    page_object_id: str,
    page_properties: Dict[str, Any],
    fields: str,
) -> str:
    """Update page (slide) properties such as background fill or page type."""
    logger.info(f"[update_page_properties] Email='{user_google_email}', Presentation={presentation_id}, Page={page_object_id}")
    req = {
        "updatePageProperties": {
            "objectId": page_object_id,
            "pageProperties": page_properties,
            "fields": fields,
        }
    }
    await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    return "Updated page properties."


@server.tool()
@handle_http_errors("update_page_element_transform", service_type="slides")
@require_google_service("slides", "slides")
async def update_page_element_transform(
    service,
    user_google_email: str, presentation_id: str,
    object_id: str,
    transform: Dict[str, Any],
    apply_mode: str = "RELATIVE",
) -> str:
    """Update the transform (position/scale/rotation) of a page element."""
    logger.info(f"[update_page_element_transform] Email='{user_google_email}', Presentation={presentation_id}, Object={object_id}")
    req = {
        "updatePageElementTransform": {
            "objectId": object_id,
            "transform": transform,
            "applyMode": apply_mode,
        }
    }
    await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    return "Updated element transform."


@server.tool()
@handle_http_errors("update_image_properties", service_type="slides")
@require_google_service("slides", "slides")
async def update_image_properties(
    service,
    user_google_email: str, presentation_id: str,
    object_id: str,
    image_properties: Dict[str, Any],
    fields: str,
) -> str:
    """Update image properties (e.g., transparency, recolor)."""
    logger.info(f"[update_image_properties] Email='{user_google_email}', Presentation={presentation_id}, Object={object_id}")
    req = {
        "updateImageProperties": {
            "objectId": object_id,
            "imageProperties": image_properties,
            "fields": fields,
        }
    }
    await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    return "Updated image properties."


@server.tool()
@handle_http_errors("refresh_sheets_chart", service_type="slides")
@require_google_service("slides", "slides")
async def refresh_sheets_chart(
    service,
    user_google_email: str, presentation_id: str,
    object_id: str,
    user_id: Optional[str] = None
) -> str:
    """Refresh a linked Sheets chart element by its object id."""
    logger.info(f"[refresh_sheets_chart] Email='{user_google_email}', Presentation={presentation_id}, Object={object_id}")
    req = {"refreshSheetsChart": {"objectId": object_id}}
    await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    return "Refreshed linked Sheets chart."


@server.tool()
@handle_http_errors("group_objects", service_type="slides")
@require_google_service("slides", "slides")
async def group_objects(
    service,
    user_google_email: str, presentation_id: str,
    object_ids: List[str],
    group_object_id: Optional[str] = None,
    user_id: Optional[str] = None,
) -> str:
    """Group multiple page elements into a single group object."""
    logger.info(f"[group_objects] Email='{user_google_email}', Presentation={presentation_id}, Count={len(object_ids)}")
    req: Dict[str, Any] = {"groupObjects": {"objects": object_ids}}
    if group_object_id:
        req["groupObjects"]["groupObjectId"] = group_object_id

    result = await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    new_id = result.get("replies", [{}])[0].get("groupObjects", {}).get("objectId")
    return f"Grouped objects into {new_id}."


@server.tool()
@handle_http_errors("ungroup_objects", service_type="slides")
@require_google_service("slides", "slides")
async def ungroup_objects(
    service,
    user_google_email: str, presentation_id: str,
    group_object_id: str,
    user_id: Optional[str] = None
) -> str:
    """Ungroup a group object back into individual elements."""
    logger.info(f"[ungroup_objects] Email='{user_google_email}', Presentation={presentation_id}, Group={group_object_id}")
    req = {"ungroupObjects": {"groupObjectId": group_object_id}}
    await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    return "Ungrouped objects."


@server.tool()
@handle_http_errors("create_sheets_chart", service_type="slides")
@require_google_service("slides", "slides")
async def create_sheets_chart(
    service,
    user_google_email: str, presentation_id: str,
    spreadsheet_id: str,
    chart_id: int,
    element_properties: Dict[str, Any],
    user_id: Optional[str] = None,
    linking_mode: Optional[str] = "LINKED",
    object_id: Optional[str] = None,
) -> str:
    """
    Embed a chart from Google Sheets into a slide.

    Args:
        spreadsheet_id: Source spreadsheet ID containing the chart.
        chart_id: The chart ID within the spreadsheet.
        element_properties: Placement/size including pageObjectId and transform/size.
        linking_mode: "LINKED" or "NOT_LINKED_IMAGE" (default: LINKED).
        object_id: Optional object id for the new element.
    """
    logger.info(f"[create_sheets_chart] Email='{user_google_email}', Presentation={presentation_id}, Sheet={spreadsheet_id}, Chart={chart_id}")
    req: Dict[str, Any] = {
        "createSheetsChart": {
            "spreadsheetId": spreadsheet_id,
            "chartId": chart_id,
            "elementProperties": element_properties,
        }
    }
    if linking_mode:
        req["createSheetsChart"]["linkingMode"] = linking_mode
    if object_id:
        req["createSheetsChart"]["objectId"] = object_id

    result = await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    new_id = result.get("replies", [{}])[0].get("createSheetsChart", {}).get("objectId")
    return f"Created Sheets chart with id {new_id}."


@server.tool()
@handle_http_errors("update_sheets_chart_spec", service_type="slides")
@require_google_service("slides", "slides")
async def update_sheets_chart_spec(
    service,
    user_google_email: str, presentation_id: str,
    object_id: str,
    fields: str,
    user_id: Optional[str] = None,
    spreadsheet_id: Optional[str] = None,
    chart_id: Optional[int] = None,
    linking_mode: Optional[str] = None,
) -> str:
    """
    Update an embedded Sheets chart specification (spreadsheetId, chartId, linkingMode).

    Args:
        object_id: The embedded Sheets chart object id on the slide.
        fields: Comma-separated fields to update (e.g., "spreadsheetId,chartId,linkingMode").
    """
    logger.info(f"[update_sheets_chart_spec] Email='{user_google_email}', Presentation={presentation_id}, Object={object_id}")
    spec: Dict[str, Any] = {"objectId": object_id}
    if spreadsheet_id is not None:
        spec["spreadsheetId"] = spreadsheet_id
    if chart_id is not None:
        spec["chartId"] = chart_id
    if linking_mode is not None:
        spec["linkingMode"] = linking_mode

    req = {"updateSheetsChartSpec": {**spec, "fields": fields}}
    await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    return "Updated Sheets chart spec."


@server.tool()
@handle_http_errors("replace_all_shapes_with_sheets_chart", service_type="slides")
@require_google_service("slides", "slides")
async def replace_all_shapes_with_sheets_chart(
    service,
    user_google_email: str, presentation_id: str,
    spreadsheet_id: str,
    chart_id: int,
    user_id: Optional[str] = None,
    linking_mode: Optional[str] = "LINKED",
    contains_text: Optional[Dict[str, Any]] = None,
    page_object_ids: Optional[List[str]] = None,
) -> str:
    """
    Replace matching shapes with a Sheets chart.

    Args:
        contains_text: Optional text match filter for shapes.
        page_object_ids: Optional page restriction list.
    """
    logger.info(f"[replace_all_shapes_with_sheets_chart] Email='{user_google_email}', Presentation={presentation_id}, Sheet={spreadsheet_id}, Chart={chart_id}")
    req: Dict[str, Any] = {
        "replaceAllShapesWithSheetsChart": {
            "spreadsheetId": spreadsheet_id,
            "chartId": chart_id,
        }
    }
    if linking_mode:
        req["replaceAllShapesWithSheetsChart"]["linkingMode"] = linking_mode
    if contains_text:
        req["replaceAllShapesWithSheetsChart"]["containsText"] = contains_text
    if page_object_ids:
        req["replaceAllShapesWithSheetsChart"]["pageObjectIds"] = page_object_ids

    result = await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    changed = result.get("replies", [{}])[0].get("replaceAllShapesWithSheetsChart", {}).get("occurrencesChanged", 0)
    return f"Replaced {changed} shape(s) with Sheets chart."


@server.tool()
@handle_http_errors("replace_all_shapes_with_image", service_type="slides")
@require_google_service("slides", "slides")
async def replace_all_shapes_with_image(
    service,
    user_google_email: str, presentation_id: str,
    image_url: str,
    image_replace_method: Optional[str] = None,
    user_id: Optional[str] = None,
    contains_text: Optional[Dict[str, Any]] = None,
    page_object_ids: Optional[List[str]] = None,
) -> str:
    """
    Replace matching shapes with an image (by URL). image_replace_method can be CENTER_CROP, FILL, etc.
    """
    logger.info(f"[replace_all_shapes_with_image] Email='{user_google_email}', Presentation={presentation_id}")
    payload: Dict[str, Any] = {"imageUrl": image_url}
    if image_replace_method:
        payload["imageReplaceMethod"] = image_replace_method
    if contains_text:
        payload["containsText"] = contains_text
    if page_object_ids:
        payload["pageObjectIds"] = page_object_ids

    req = {"replaceAllShapesWithImage": payload}
    result = await asyncio.to_thread(
        service.presentations().batchUpdate(presentationId=presentation_id, body={"requests": [req]}).execute
    )
    changed = result.get("replies", [{}])[0].get("replaceAllShapesWithImage", {}).get("occurrencesChanged", 0)
    return f"Replaced {changed} shape(s) with image."

# Create comment management tools for slides
_comment_tools = create_comment_tools("presentation", "presentation_id")
read_presentation_comments = _comment_tools['read_comments']
create_presentation_comment = _comment_tools['create_comment']
reply_to_presentation_comment = _comment_tools['reply_to_comment']
resolve_presentation_comment = _comment_tools['resolve_comment']

# Aliases for backwards compatibility and intuitive naming
read_slide_comments = read_presentation_comments
create_slide_comment = create_presentation_comment
reply_to_slide_comment = reply_to_presentation_comment
resolve_slide_comment = resolve_presentation_comment
