"""
EOM Inventory Report PDF Generator
Generates branded PDF reports for end-of-month inventory.
Optimized to fit on single page when possible.
"""
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from datetime import datetime


def generate_eom_inventory_pdf(report_data):
    """
    Generate branded PDF for EOM inventory report.
    Optimized for single-page output when possible.

    Args:
        report_data: Dict containing:
            - from_date: Start date (ISO format or None)
            - to_date: End date (ISO format or None)
            - generated_at: Generation timestamp
            - products: List of product dicts with beginning/shipped/ending
            - totals: Summary totals

    Returns:
        bytes: PDF file content
    """
    buffer = io.BytesIO()

    # Tighter margins to maximize space
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.4 * inch,
        leftMargin=0.4 * inch,
        topMargin=0.35 * inch,
        bottomMargin=0.35 * inch
    )

    story = []
    styles = getSampleStyleSheet()

    # Compact custom styles
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#000000'),
        spaceAfter=0,
        spaceBefore=0,
        fontName='Helvetica-Bold'
    )

    subheader_style = ParagraphStyle(
        'CustomSubheader',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#666666'),
        spaceAfter=0,
        spaceBefore=0
    )

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=14,
        textColor=colors.HexColor('#000000'),
        spaceAfter=2,
        spaceBefore=4,
        fontName='Helvetica-Bold'
    )

    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#666666'),
        spaceAfter=0,
        spaceBefore=0
    )

    section_title_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=10,
        textColor=colors.HexColor('#000000'),
        spaceAfter=3,
        spaceBefore=6,
        fontName='Helvetica-Bold'
    )

    small_style = ParagraphStyle(
        'SmallText',
        parent=styles['Normal'],
        fontSize=8,
        spaceAfter=0,
        spaceBefore=0
    )

    # Compact header - all on fewer lines
    header_table_data = [
        [
            Paragraph("CBRT", header_style),
            Paragraph("INVENTORY REPORT", title_style)
        ],
        [
            Paragraph("Cincinnati Barge & Rail Terminal, LLC<br/>1707 Riverside Drive, Cincinnati, Ohio 45202", subheader_style),
            ''
        ]
    ]
    header_table = Table(header_table_data, colWidths=[4.0 * inch, 3.7 * inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(header_table)

    # Thin horizontal line
    line_table = Table([['']], colWidths=[7.7 * inch])
    line_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 1.5, colors.black),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 0.08 * inch))

    # Date range and generated info - compact
    from_date = report_data.get('from_date')
    to_date = report_data.get('to_date')
    if from_date and to_date:
        date_range = f"Period: {_format_date(from_date)} - {_format_date(to_date)}"
    elif from_date:
        date_range = f"From: {_format_date(from_date)}"
    elif to_date:
        date_range = f"Through: {_format_date(to_date)}"
    else:
        date_range = "All Time"

    generated_at = report_data.get('generated_at', '')
    if generated_at:
        try:
            gen_dt = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
            generated_str = gen_dt.strftime('%b %d, %Y %I:%M %p')
        except Exception:
            generated_str = generated_at
    else:
        generated_str = datetime.now().strftime('%b %d, %Y %I:%M %p')

    # Prepared for + dates in compact two-column layout
    info_table_data = [
        [
            Paragraph("<b>PREPARED FOR:</b> Primetrade, LLC, 11440 Carmel Commons Blvd, Suite 200, Charlotte, NC 28226", small_style),
            Paragraph(f"{date_range}<br/>Generated: {generated_str}", date_style)
        ]
    ]
    info_table = Table(info_table_data, colWidths=[5.0 * inch, 2.7 * inch])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.1 * inch))

    # Inventory summary section
    story.append(Paragraph("INVENTORY SUMMARY", section_title_style))

    products = report_data.get('products', [])
    totals = report_data.get('totals', {})

    # Build compact summary table
    summary_data = [
        [
            Paragraph("<b>Product</b>", small_style),
            Paragraph("<b>Beginning</b>", small_style),
            Paragraph("<b>Shipped</b>", small_style),
            Paragraph("<b>Ending</b>", small_style),
        ]
    ]

    for product in products:
        summary_data.append([
            product.get('name', ''),
            _format_tons(product.get('beginning_inventory', 0)),
            _format_tons(product.get('shipped_this_period', 0)),
            _format_tons(product.get('ending_inventory', 0)),
        ])

    # Totals row
    summary_data.append([
        Paragraph("<b>TOTALS</b>", small_style),
        Paragraph(f"<b>{_format_tons(totals.get('beginning_inventory', 0))}</b>", small_style),
        Paragraph(f"<b>{_format_tons(totals.get('shipped_this_period', 0))}</b>", small_style),
        Paragraph(f"<b>{_format_tons(totals.get('ending_inventory', 0))}</b>", small_style),
    ])

    summary_table = Table(summary_data, colWidths=[3.2 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch])
    summary_table.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F5F5F5')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E5E7EB')),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 0.1 * inch))

    # Shipment details by product - more compact
    for product in products:
        bols = product.get('bols', [])
        if not bols:
            continue

        # Keep section title and table together
        section_elements = []
        section_elements.append(Paragraph(f"SHIPMENTS: {product.get('name', '')}", section_title_style))

        detail_data = [
            [
                Paragraph("<b>BOL #</b>", small_style),
                Paragraph("<b>Date</b>", small_style),
                Paragraph("<b>Customer</b>", small_style),
                Paragraph("<b>Release</b>", small_style),
                Paragraph("<b>Weight</b>", small_style),
            ]
        ]

        for bol in bols:
            weight_str = _format_tons(bol.get('weight_tons', 0))

            detail_data.append([
                bol.get('bol_number', ''),
                _format_date(bol.get('date', '')),
                bol.get('customer', '')[:25],  # Truncate
                bol.get('release_number', ''),
                weight_str,
            ])

        detail_table = Table(detail_data, colWidths=[1.1 * inch, 0.8 * inch, 2.8 * inch, 0.9 * inch, 1.1 * inch])
        detail_table.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#DDDDDD')),
            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#EEEEEE')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F8FAFC')),
            ('ALIGN', (4, 0), (4, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
        ]))
        section_elements.append(detail_table)
        section_elements.append(Spacer(1, 0.08 * inch))

        # Try to keep together, but allow split if needed
        story.append(KeepTogether(section_elements))

    # Compact footer
    story.append(Spacer(1, 0.05 * inch))

    legend_style = ParagraphStyle(
        'Legend',
        parent=styles['Normal'],
        fontSize=7,
        textColor=colors.HexColor('#888888'),
    )
    story.append(Paragraph("All weights are CBRT scale weights (net tons)", legend_style))

    story.append(Spacer(1, 0.05 * inch))
    story.append(line_table)

    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=7,
        textColor=colors.HexColor('#888888'),
        alignment=TA_CENTER,
        spaceBefore=2
    )
    story.append(Paragraph(
        "This document certifies inventory movements for the period shown. Contact Cincinnati Barge & Rail Terminal, LLC for questions.",
        footer_style
    ))

    # Build PDF
    doc.build(story)

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def _format_date(date_str):
    """Format date string for display."""
    if not date_str:
        return ''
    try:
        if 'T' in str(date_str):
            date_str = date_str.split('T')[0]
        if '-' in str(date_str):
            parts = date_str.split('-')
            if len(parts) == 3:
                return f"{parts[1]}/{parts[2]}/{parts[0]}"
        return str(date_str)
    except Exception:
        return str(date_str)


def _format_tons(value):
    """Format tons value with commas and 2 decimal places."""
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "0.00"
