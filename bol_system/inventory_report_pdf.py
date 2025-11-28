"""
EOM Inventory Report PDF Generator
Generates branded PDF reports for end-of-month inventory.
"""
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from datetime import datetime


def generate_eom_inventory_pdf(report_data):
    """
    Generate branded PDF for EOM inventory report.

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

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.5 * inch,
        leftMargin=0.5 * inch,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch
    )

    story = []
    styles = getSampleStyleSheet()

    # Custom styles
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#000000'),
        spaceAfter=2,
        fontName='Helvetica-Bold'
    )

    subheader_style = ParagraphStyle(
        'CustomSubheader',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#666666'),
        spaceAfter=1
    )

    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#000000'),
        spaceAfter=4,
        spaceBefore=6,
        fontName='Helvetica-Bold'
    )

    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#666666')
    )

    section_title_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=11,
        textColor=colors.HexColor('#000000'),
        spaceAfter=6,
        spaceBefore=10,
        fontName='Helvetica-Bold'
    )

    # Header
    story.append(Paragraph("CBRT", header_style))
    story.append(Paragraph("Cincinnati Barge & Rail Terminal, LLC", subheader_style))
    story.append(Paragraph("1707 Riverside Drive, Cincinnati, Ohio 45202", subheader_style))
    story.append(Spacer(1, 0.1 * inch))

    # Horizontal line
    line_table = Table([['']], colWidths=[7.5 * inch])
    line_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 2, colors.black),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 0.1 * inch))

    # Title and date range
    story.append(Paragraph("INVENTORY REPORT", title_style))

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
            generated_str = gen_dt.strftime('%B %d, %Y at %I:%M %p')
        except Exception:
            generated_str = generated_at
    else:
        generated_str = datetime.now().strftime('%B %d, %Y at %I:%M %p')

    story.append(Paragraph(date_range, date_style))
    story.append(Paragraph(f"Generated: {generated_str}", date_style))
    story.append(Spacer(1, 0.15 * inch))

    # Prepared for section
    prepared_data = [
        [Paragraph(
            "<b>PREPARED FOR</b><br/><br/>Primetrade, LLC<br/>11440 Carmel Commons Blvd.<br/>Suite 200<br/>Charlotte, NC 28226",
            styles['Normal']
        )]
    ]
    prepared_table = Table(prepared_data, colWidths=[7.5 * inch])
    prepared_table.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 15),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEAFTER', (0, 0), (0, -1), 3, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(prepared_table)
    story.append(Spacer(1, 0.15 * inch))

    # Inventory summary section
    story.append(Paragraph("INVENTORY SUMMARY", section_title_style))

    products = report_data.get('products', [])
    totals = report_data.get('totals', {})

    # Build summary table
    summary_data = [
        [
            Paragraph("<b>Product</b>", styles['Normal']),
            Paragraph("<b>Beginning</b>", styles['Normal']),
            Paragraph("<b>Shipped</b>", styles['Normal']),
            Paragraph("<b>Ending</b>", styles['Normal']),
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
        Paragraph("<b>TOTALS</b>", styles['Normal']),
        Paragraph(f"<b>{_format_tons(totals.get('beginning_inventory', 0))}</b>", styles['Normal']),
        Paragraph(f"<b>{_format_tons(totals.get('shipped_this_period', 0))}</b>", styles['Normal']),
        Paragraph(f"<b>{_format_tons(totals.get('ending_inventory', 0))}</b>", styles['Normal']),
    ])

    summary_table = Table(summary_data, colWidths=[3.0 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch])
    summary_table.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
        ('INNERGRID', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F5F5F5')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#E5E7EB')),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 0.2 * inch))

    # Shipment details by product
    for product in products:
        bols = product.get('bols', [])
        if not bols:
            continue

        story.append(Paragraph(f"SHIPMENTS: {product.get('name', '')}", section_title_style))

        detail_data = [
            [
                Paragraph("<b>BOL #</b>", styles['Normal']),
                Paragraph("<b>Date</b>", styles['Normal']),
                Paragraph("<b>Customer</b>", styles['Normal']),
                Paragraph("<b>Release</b>", styles['Normal']),
                Paragraph("<b>Weight (tons)</b>", styles['Normal']),
            ]
        ]

        for bol in bols:
            weight_str = _format_tons(bol.get('weight_tons', 0))
            if bol.get('is_official'):
                weight_str += ' *'  # Mark official weights

            detail_data.append([
                bol.get('bol_number', ''),
                _format_date(bol.get('date', '')),
                bol.get('customer', '')[:30],  # Truncate long names
                bol.get('release_number', ''),
                weight_str,
            ])

        detail_table = Table(detail_data, colWidths=[1.2 * inch, 0.9 * inch, 2.5 * inch, 1.0 * inch, 1.4 * inch])
        detail_table.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#DDDDDD')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#EEEEEE')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F8FAFC')),
            ('ALIGN', (4, 0), (4, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        story.append(detail_table)
        story.append(Spacer(1, 0.15 * inch))

    # Legend
    story.append(Spacer(1, 0.1 * inch))
    legend_style = ParagraphStyle(
        'Legend',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#666666'),
    )
    story.append(Paragraph("* Indicates official (certified scale) weight", legend_style))

    # Bottom line
    story.append(Spacer(1, 0.15 * inch))
    story.append(line_table)
    story.append(Spacer(1, 0.1 * inch))

    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#666666'),
        alignment=TA_CENTER
    )
    story.append(Paragraph(
        "This document certifies the inventory movements for the period shown above.",
        footer_style
    ))
    story.append(Paragraph(
        "For questions, please contact Cincinnati Barge & Rail Terminal, LLC.",
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
        # Handle ISO format
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
