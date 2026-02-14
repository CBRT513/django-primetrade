"""
Weight Variance Report PDF Generator
Generates branded PDF using ReportLab. Follows inventory_report_pdf.py patterns.
"""
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from datetime import datetime


def generate_variance_pdf(report_data):
    """
    Generate branded PDF for weight variance report.

    Args:
        report_data: dict from compute_variance_report() plus 'product_name' and 'generated_at'.

    Returns:
        bytes: PDF file content
    """
    buffer = io.BytesIO()

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

    # Custom styles
    header_style = ParagraphStyle(
        'CustomHeader', parent=styles['Heading1'],
        fontSize=20, textColor=colors.HexColor('#000000'),
        spaceAfter=0, spaceBefore=0, fontName='Helvetica-Bold'
    )
    subheader_style = ParagraphStyle(
        'CustomSubheader', parent=styles['Normal'],
        fontSize=8, textColor=colors.HexColor('#666666'),
        spaceAfter=0, spaceBefore=0
    )
    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Heading1'],
        fontSize=14, textColor=colors.HexColor('#000000'),
        spaceAfter=2, spaceBefore=4, fontName='Helvetica-Bold'
    )
    section_style = ParagraphStyle(
        'SectionTitle', parent=styles['Heading2'],
        fontSize=10, textColor=colors.HexColor('#000000'),
        spaceAfter=3, spaceBefore=8, fontName='Helvetica-Bold'
    )
    small_style = ParagraphStyle(
        'SmallText', parent=styles['Normal'],
        fontSize=8, spaceAfter=0, spaceBefore=0
    )
    note_style = ParagraphStyle(
        'NoteText', parent=styles['Normal'],
        fontSize=7, textColor=colors.HexColor('#888888'),
        spaceAfter=0, spaceBefore=2
    )

    product_name = report_data.get('product_name', '')
    summary = report_data.get('summary', {})
    accuracy = report_data.get('accuracy', {})
    inventory = report_data.get('inventory', {})
    carriers = report_data.get('carriers', [])
    buyers = report_data.get('buyers', [])
    outliers = report_data.get('outliers', [])
    missing = report_data.get('missing', [])

    # --- Header ---
    header_table_data = [
        [
            Paragraph("CBRT", header_style),
            Paragraph("WEIGHT VARIANCE REPORT", title_style)
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

    line_table = Table([['']], colWidths=[7.7 * inch])
    line_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 1.5, colors.black),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 0.08 * inch))

    # Product + date info
    generated_str = datetime.now().strftime('%b %d, %Y %I:%M %p')
    info_data = [[
        Paragraph(f"<b>Product:</b> {product_name}", small_style),
        Paragraph(f"Generated: {generated_str}", ParagraphStyle(
            'DateRight', parent=styles['Normal'],
            fontSize=9, alignment=TA_RIGHT, textColor=colors.HexColor('#666666'),
        ))
    ]]
    info_table = Table(info_data, colWidths=[5.0 * inch, 2.7 * inch])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.1 * inch))

    # --- Executive Summary ---
    story.append(Paragraph("EXECUTIVE SUMMARY", section_style))
    summary_data = [
        [_b("Total BOLs", small_style), str(summary.get('total_bols', 0)),
         _b("With Official", small_style), str(summary.get('with_official', 0))],
        [_b("Missing Official", small_style), str(summary.get('without_official', 0)),
         _b("Coverage", small_style), f"{summary.get('coverage_pct', 0)}%"],
    ]
    t = Table(summary_data, colWidths=[1.5 * inch, 1.0 * inch, 1.5 * inch, 1.0 * inch])
    t.setStyle(_grid_style())
    story.append(t)
    story.append(Spacer(1, 0.1 * inch))

    # --- Accuracy ---
    if accuracy.get('has_data'):
        story.append(Paragraph("BUCKET WEIGHT ACCURACY", section_style))
        acc_data = [
            [_b("Dataset", small_style), _b("Count", small_style), _b("Mean %", small_style),
             _b("Median %", small_style), _b("Std Dev %", small_style),
             _b("Heavier", small_style), _b("Lighter", small_style)],
        ]
        a = accuracy.get('all', {})
        acc_data.append([
            "All Paired", str(a.get('count', 0)),
            f"{a.get('mean', 0)}%", f"{a.get('median', 0)}%",
            f"{a.get('stdev', '—')}%" if a.get('stdev') is not None else "—",
            str(accuracy.get('all_count_heavier', 0)),
            str(accuracy.get('all_count_lighter', 0)),
        ])
        if accuracy.get('has_clean'):
            c = accuracy.get('clean', {})
            acc_data.append([
                "Clean (≤5%)", str(c.get('count', 0)),
                f"{c.get('mean', 0)}%", f"{c.get('median', 0)}%",
                f"{c.get('stdev', '—')}%" if c.get('stdev') is not None else "—",
                str(accuracy.get('clean_count_heavier', 0)),
                str(accuracy.get('clean_count_lighter', 0)),
            ])
        t = Table(acc_data, colWidths=[1.1 * inch, 0.7 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 0.8 * inch, 0.8 * inch])
        t.setStyle(_grid_style())
        story.append(t)
        story.append(Paragraph("Positive = official heavier than bucket. Negative = official lighter.", note_style))
        story.append(Spacer(1, 0.1 * inch))

    # --- Inventory Comparison ---
    story.append(Paragraph("INVENTORY COMPARISON", section_style))
    inv_data = [
        [_b("Scenario", small_style), _b("Shipped", small_style),
         _b("Remaining", small_style), _b("Method", small_style)],
        ["Bucket Only", _fmt(inventory.get('bucket_shipped')), _fmt(inventory.get('bucket_remaining')), "sum(net_tons)"],
        ["Hybrid", _fmt(inventory.get('hybrid_shipped')), _fmt(inventory.get('hybrid_remaining')), "official ?? bucket"],
        ["Best Estimate", _fmt(inventory.get('best_shipped')), _fmt(inventory.get('best_remaining')),
         f"hybrid + {inventory.get('correction_factor', 0)}% correction"],
    ]
    t = Table(inv_data, colWidths=[1.5 * inch, 1.3 * inch, 1.3 * inch, 3.6 * inch])
    t.setStyle(_grid_style())
    story.append(t)
    story.append(Paragraph(f"Starting inventory: {_fmt(inventory.get('start_tons'))} tons", note_style))
    story.append(Spacer(1, 0.1 * inch))

    # --- Carrier Variance ---
    if carriers:
        elements = []
        elements.append(Paragraph("CARRIER VARIANCE", section_style))
        car_data = [
            [_b("Carrier", small_style), _b("BOLs", small_style), _b("Avg %", small_style),
             _b("Min %", small_style), _b("Max %", small_style)],
        ]
        for c in carriers:
            car_data.append([
                c['carrier_name'], str(c['bol_count']),
                f"{c['avg_variance_pct']}%", f"{c['min_variance_pct']}%", f"{c['max_variance_pct']}%",
            ])
        t = Table(car_data, colWidths=[2.5 * inch, 0.8 * inch, 1.0 * inch, 1.0 * inch, 1.0 * inch])
        t.setStyle(_grid_style())
        elements.append(t)
        elements.append(Spacer(1, 0.1 * inch))
        story.append(KeepTogether(elements))

    # --- Buyer Summary ---
    if buyers:
        elements = []
        elements.append(Paragraph("BUYER SUMMARY", section_style))
        buy_data = [
            [_b("Buyer", small_style), _b("BOLs", small_style), _b("Total Net Tons", small_style)],
        ]
        for b in buyers:
            buy_data.append([b['buyer_name'], str(b['bol_count']), _fmt(b['total_net_tons'])])
        t = Table(buy_data, colWidths=[3.5 * inch, 1.0 * inch, 1.5 * inch])
        t.setStyle(_grid_style())
        elements.append(t)
        elements.append(Spacer(1, 0.1 * inch))
        story.append(KeepTogether(elements))

    # --- Outliers ---
    if outliers:
        story.append(Paragraph("FLAGGED OUTLIERS (>5% VARIANCE)", section_style))
        out_data = [
            [_b("BOL #", small_style), _b("Date", small_style), _b("Bucket", small_style),
             _b("Official", small_style), _b("Var %", small_style), _b("Cause", small_style)],
        ]
        for o in outliers[:20]:  # Cap at 20 for PDF
            out_data.append([
                o['bol_number'], _format_date(o.get('date', '')),
                _fmt(o['net_tons']), _fmt(o['official_tons']),
                f"{o['variance_pct']}%", o['cause'],
            ])
        t = Table(out_data, colWidths=[1.0 * inch, 0.8 * inch, 0.9 * inch, 0.9 * inch, 0.8 * inch, 3.3 * inch])
        t.setStyle(_grid_style())
        story.append(t)
        if len(outliers) > 20:
            story.append(Paragraph(f"Showing 20 of {len(outliers)} outliers. See HTML report for full list.", note_style))
        story.append(Spacer(1, 0.1 * inch))

    # --- Missing ---
    if missing:
        story.append(Paragraph(f"MISSING OFFICIAL WEIGHTS ({len(missing)})", section_style))
        mis_data = [
            [_b("BOL #", small_style), _b("Date", small_style), _b("Buyer", small_style),
             _b("Carrier", small_style), _b("Bucket (tons)", small_style)],
        ]
        for m in missing[:30]:  # Cap at 30 for PDF
            mis_data.append([
                m['bol_number'], _format_date(m.get('date', '')),
                m.get('buyer_name', '')[:25], m.get('carrier_name', '')[:25],
                _fmt(m['net_tons']),
            ])
        t = Table(mis_data, colWidths=[1.1 * inch, 0.8 * inch, 2.5 * inch, 2.0 * inch, 1.3 * inch])
        t.setStyle(_grid_style())
        story.append(t)
        if len(missing) > 30:
            story.append(Paragraph(f"Showing 30 of {len(missing)}. See HTML report for full list.", note_style))

    # --- Footer ---
    story.append(Spacer(1, 0.15 * inch))
    story.append(line_table)
    footer_style = ParagraphStyle(
        'Footer', parent=styles['Normal'],
        fontSize=7, textColor=colors.HexColor('#888888'),
        alignment=TA_CENTER, spaceBefore=2
    )
    story.append(Paragraph(
        "Weight Variance Report — Cincinnati Barge & Rail Terminal, LLC. Contact CBRT for questions.",
        footer_style
    ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def _b(text, style):
    """Bold paragraph helper."""
    return Paragraph(f"<b>{text}</b>", style)


def _fmt(value):
    """Format number with commas and 2 decimal places."""
    try:
        return f"{float(value):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _format_date(date_str):
    """Format date string for display."""
    if not date_str:
        return ''
    try:
        if '-' in str(date_str):
            parts = date_str.split('-')
            if len(parts) == 3:
                return f"{parts[1]}/{parts[2]}/{parts[0]}"
        return str(date_str)
    except Exception:
        return str(date_str)


def _grid_style():
    """Standard table grid style."""
    return TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F5F5F5')),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ])
