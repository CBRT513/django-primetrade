#!/usr/bin/env python3
"""
Generate branded inventory report for Primetrade
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from datetime import datetime

def generate_inventory_report(output_path, report_date, product, lot_number, quantity, chemistry):
    """
    Generate inventory report PDF

    Args:
        output_path: Path to save PDF
        report_date: Date string (e.g., "October 31, 2025")
        product: Product name (e.g., "Nodular Pig Iron")
        lot_number: Lot number (e.g., "CRT-050N-711-A")
        quantity: Quantity string (e.g., "3,129.72 Net Tons")
        chemistry: Dict with keys C, Si, S, P, Mn (values as strings with %)
    """
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )

    story = []
    styles = getSampleStyleSheet()

    # Custom styles
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading1'],
        fontSize=28,
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
        fontSize=20,
        textColor=colors.HexColor('#000000'),
        spaceAfter=6,
        spaceBefore=8,
        fontName='Helvetica-Bold'
    )

    section_title_style = ParagraphStyle(
        'SectionTitle',
        parent=styles['Heading2'],
        fontSize=11,
        textColor=colors.HexColor('#000000'),
        spaceAfter=8,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )

    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_RIGHT,
        textColor=colors.HexColor('#666666')
    )

    # Header
    story.append(Paragraph("CBRT", header_style))
    story.append(Paragraph("Cincinnati Barge & Rail Terminal, LLC", subheader_style))
    story.append(Paragraph("1707 Riverside Drive", subheader_style))
    story.append(Paragraph("Cincinnati, Ohio 45202", subheader_style))
    story.append(Spacer(1, 0.15*inch))

    # Horizontal line
    line_table = Table([['']], colWidths=[6.5*inch])
    line_table.setStyle(TableStyle([
        ('LINEBELOW', (0, 0), (-1, -1), 2, colors.black),
    ]))
    story.append(line_table)
    story.append(Spacer(1, 0.15*inch))

    # Title and date
    story.append(Paragraph("INVENTORY REPORT", title_style))
    story.append(Paragraph(f"Report Date: {report_date}", date_style))
    story.append(Spacer(1, 0.15*inch))

    # Prepared for section (with left border)
    prepared_data = [
        [Paragraph("<b>PREPARED FOR</b><br/><br/>Primetrade, LLC<br/>11440 Carmel Commons Blvd.<br/>Suite 200<br/>Charlotte, NC 28226", styles['Normal'])]
    ]
    prepared_table = Table(prepared_data, colWidths=[6.5*inch])
    prepared_table.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 15),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LINEAFTER', (0, 0), (0, -1), 3, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(prepared_table)
    story.append(Spacer(1, 0.15*inch))

    # Product information
    story.append(Paragraph("PRODUCT INFORMATION", section_title_style))

    product_data = [
        [
            Paragraph("<font color='#999999'>PRODUCT DESCRIPTION</font>", styles['Normal']),
            Paragraph("<font color='#999999'>LOT NUMBER</font>", styles['Normal']),
            Paragraph("<font color='#999999'>QUANTITY ON-HAND</font>", styles['Normal'])
        ],
        [
            Paragraph(f"<b>{product}</b>", styles['Normal']),
            Paragraph(f"<b>{lot_number}</b>", styles['Normal']),
            Paragraph(f"<b>{quantity}</b>", styles['Normal'])
        ]
    ]

    product_table = Table(product_data, colWidths=[2.2*inch, 2.2*inch, 2.1*inch])
    product_table.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 1), (-1, 1), 2, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(product_table)
    story.append(Spacer(1, 0.15*inch))

    # Chemical analysis
    story.append(Paragraph("CHEMICAL ANALYSIS", section_title_style))

    chem_data = [
        [
            Paragraph("<font color='#666666'>ELEMENT</font>", styles['Normal']),
            Paragraph("<font color='#666666'>PERCENTAGE</font>", styles['Normal'])
        ],
        ['C', chemistry.get('C', '')],
        ['Si', chemistry.get('Si', '')],
        ['S', chemistry.get('S', '')],
        ['P', chemistry.get('P', '')],
        ['Mn', chemistry.get('Mn', '')],
    ]

    chem_table = Table(chem_data, colWidths=[3.25*inch, 3.25*inch])
    chem_table.setStyle(TableStyle([
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
        ('INNERGRID', (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F5F5F5')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
    ]))
    story.append(chem_table)
    story.append(Spacer(1, 0.25*inch))

    # Bottom line
    story.append(line_table)
    story.append(Spacer(1, 0.15*inch))

    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#666666'),
        alignment=TA_CENTER
    )
    story.append(Paragraph(
        "This document certifies the inventory on-hand as of the report date shown above.",
        footer_style
    ))
    story.append(Paragraph(
        "For questions regarding this inventory report, please contact Cincinnati Barge & Rail Terminal, LLC.",
        footer_style
    ))

    # Build PDF
    doc.build(story)
    print(f"✓ Inventory report generated: {output_path}")


if __name__ == '__main__':
    # Generate the report with updated values
    generate_inventory_report(
        output_path='/Users/cerion/Downloads/Inventory_Report_Nodular_Pig_Iron_Oct31_2025.pdf',
        report_date='October 31, 2025',
        product='Nodular Pig Iron',
        lot_number='CRT-050N-711-A',
        quantity='3,129.72 Net Tons',
        chemistry={
            'C': '4.286%',
            'Si': '0.025%',
            'S': '0.011%',
            'P': '0.038%',
            'Mn': '0.027%'
        }
    )
