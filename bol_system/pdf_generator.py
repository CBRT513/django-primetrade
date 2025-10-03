"""
BOL PDF Generation using ReportLab
Matches the design from bol.html
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
import os
from django.conf import settings


def generate_bol_pdf(bol):
    """
    Generate a PDF for a BOL object
    Returns the file path relative to MEDIA_ROOT
    """
    # Ensure directory exists
    pdf_dir = os.path.join(settings.MEDIA_ROOT, 'bol_pdfs')
    os.makedirs(pdf_dir, exist_ok=True)

    # Generate filename
    filename = f"{bol.bol_number}.pdf"
    filepath = os.path.join(pdf_dir, filename)

    # Create PDF
    doc = SimpleDocTemplate(
        filepath,
        pagesize=letter,
        rightMargin=0.4*inch,
        leftMargin=0.4*inch,
        topMargin=0.4*inch,
        bottomMargin=0.4*inch
    )

    # Container for elements
    elements = []

    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=36,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceAfter=12
    )

    bar_style = ParagraphStyle(
        'Bar',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        textColor=colors.black
    )

    # Title
    elements.append(Paragraph("BILL OF LADING", title_style))
    elements.append(Spacer(1, 0.1*inch))

    # Header table (Ship From + Info Grid)
    header_data = [
        [
            {
                'content': Paragraph('<para align="center" fontName="Helvetica-Bold">SHIP FROM:</para>', styles['Normal']),
                'span': (0, 0, 5, 0)
            },
            {
                'content': Paragraph('<para align="right"><b>Page 1 of 1</b></para>', styles['Normal']),
                'span': (6, 0, 11, 0)
            }
        ]
    ]

    # Company info block + BOL details grid
    company_info = """<para align="center" spaceBefore="10" spaceAfter="10">
    <b>Cincinnati Barge & Rail Terminal, LLC</b><br/>
    1707 Riverside Drive<br/>
    Cincinnati, Ohio 45202<br/>
    www.barge2rail.com<br/>
    <b>C/O PrimeTrade, LLC</b>
    </para>"""

    # Format date
    try:
        date_obj = datetime.strptime(bol.date, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%m/%d/%Y')
    except:
        formatted_date = bol.date

    # Build info grid (6 rows, right half of page)
    info_grid = [
        ['BOL Number:', f'<b>{bol.bol_number}</b>'],
        ['Customer PO#:', bol.customer_po or ''],
        ['Carrier:', bol.carrier_name],
        ['Truck #:', bol.truck_number],
        ['Trailer #:', bol.trailer_number],
        ['Loaded Date:', formatted_date]
    ]

    # Create the company + info section
    company_and_info_data = [
        [
            {'content': Paragraph(company_info, styles['Normal']), 'span': (0, 0, 0, 5)},  # Spans 6 rows
            'BOL Number:', f'<b>{bol.bol_number}</b>'
        ],
        ['', '', 'Customer PO#:', bol.customer_po or ''],
        ['', '', 'Carrier:', bol.carrier_name],
        ['', '', 'Truck #:', bol.truck_number],
        ['', '', 'Trailer #:', bol.trailer_number],
        ['', '', 'Loaded Date:', formatted_date]
    ]

    # Ship To section
    ship_to_text = bol.buyer_name
    if bol.ship_to:
        ship_to_text += '\n' + bol.ship_to

    # Product and weights
    total_weight_lbs = int(bol.total_weight_lbs)
    net_tons = float(bol.net_tons)

    # Build the main table data
    table_data = [
        # Header row
        ['SHIP FROM:', '', '', '', '', '', 'Page 1 of 1', '', '', '', '', ''],

        # Company info row (spans 6 rows for company, 6 cols for info on right)
        [company_info, '', '', '', '', '', 'BOL Number:', '', '', f'{bol.bol_number}', '', ''],
        ['', '', '', '', '', '', 'Customer PO#:', '', '', bol.customer_po or '', '', ''],
        ['', '', '', '', '', '', 'Carrier:', '', '', bol.carrier_name, '', ''],
        ['', '', '', '', '', '', 'Truck #:', '', '', bol.truck_number, '', ''],
        ['', '', '', '', '', '', 'Trailer #:', '', '', bol.trailer_number, '', ''],
        ['', '', '', '', '', '', 'Loaded Date:', '', '', formatted_date, '', ''],

        # Ship To header
        ['SHIP TO:', '', '', '', '', '', '', '', '', '', '', ''],

        # Ship To content
        [ship_to_text, '', '', '', '', '', '', '', '', '', '', ''],

        # Product header
        ['Lot Number: CRT-050N-711A', '', '', '', bol.product_name, '', '', '', '', '', '', ''],

        # Analysis and weights section (merged cells for layout)
        ['Analysis:\nC 4.244%\nSi 0.05%\nS 0.018%\nP 0.026%\nMn 0.013%', '', '', '',
         f'Total Weight\n{total_weight_lbs:,} LBS\n\nNet Tons\n{net_tons:.2f} N.T.', '', '', '', '', '', '', ''],

        # Note
        ['NOTE: Liability Limitation for loss or damage in this shipment may be applicable. See 49 U.S.C. § 14706(c)(1)(A) and (B). Non-hazardous',
         '', '', '', '', '', '', '', '', '', '', ''],

        # Signatures section
        ['SHIPPER SIGNATURE\nJames Rose\n\nThis is to certify that the above named materials are properly classified, packaged, marked and labeled.',
         '', '', '',
         'Trailer Loaded:\n• By Shipper\n• By Driver\n\nFreight Counted:\n• By Shipper\n• By Driver',
         '', '', '',
         'CARRIER SIGNATURE\n\n___________________________',
         '', '', '']
    ]

    # Simplified approach - use a simpler table structure
    main_table_data = []

    # Title row (already added above)

    # Header bar
    main_table_data.append([
        Paragraph('<para align="center" fontName="Helvetica-Bold" backColor="#d9d9d9">SHIP FROM:</para>', styles['Normal']),
        Paragraph('<para align="right" fontName="Helvetica-Bold" backColor="#d9d9d9">Page 1 of 1</para>', styles['Normal'])
    ])

    # Company info and BOL details side by side
    main_table_data.append([
        Paragraph(company_info, styles['Normal']),
        Table([
            [Paragraph('<para align="right" fontName="Helvetica-Bold">BOL Number:</para>', styles['Normal']),
             Paragraph(f'<para fontName="Helvetica-Bold" fontSize="13">{bol.bol_number}</para>', styles['Normal'])],
            [Paragraph('<para align="right" fontName="Helvetica-Bold">Customer PO#:</para>', styles['Normal']),
             bol.customer_po or ''],
            [Paragraph('<para align="right" fontName="Helvetica-Bold">Carrier:</para>', styles['Normal']),
             bol.carrier_name],
            [Paragraph('<para align="right" fontName="Helvetica-Bold">Truck #:</para>', styles['Normal']),
             bol.truck_number],
            [Paragraph('<para align="right" fontName="Helvetica-Bold">Trailer #:</para>', styles['Normal']),
             bol.trailer_number],
            [Paragraph('<para align="right" fontName="Helvetica-Bold">Loaded Date:</para>', styles['Normal']),
             formatted_date]
        ], colWidths=[2*inch, 1.5*inch], style=TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
    ])

    # Ship To bar
    main_table_data.append([
        Paragraph('<para align="center" fontName="Helvetica-Bold" backColor="#d9d9d9">SHIP TO:</para>',
                  bar_style), ''
    ])

    # Ship To content
    main_table_data.append([
        Paragraph(f'<para align="center" fontSize="14"><b>{ship_to_text}</b></para>', styles['Normal']), ''
    ])

    # Product bar
    main_table_data.append([
        Paragraph(f'<para align="center" fontName="Helvetica-Bold" backColor="#d9d9d9">Lot Number: CRT-050N-711A</para>', bar_style),
        Paragraph(f'<para align="center" fontName="Helvetica-Bold" backColor="#d9d9d9">{bol.product_name}</para>', bar_style)
    ])

    # Analysis and weights
    analysis_text = """<para align="center" fontSize="14">
    <b>Analysis:</b><br/>
    <b>C 4.244%</b><br/>
    <b>Si 0.05%</b><br/>
    <b>S 0.018%</b><br/>
    <b>P 0.026%</b><br/>
    <b>Mn 0.013%</b>
    </para>"""

    weight_text = f"""<para align="center">
    <b><font size="18">Total Weight</font></b><br/>
    <font size="24"><b>{total_weight_lbs:,}</b></font><br/>
    <font size="12">LBS</font><br/>
    <br/>
    <b><font size="18">Net Tons</font></b><br/>
    <font size="24"><b>{net_tons:.2f}</b></font><br/>
    <font size="12">N.T.</font>
    </para>"""

    main_table_data.append([
        Paragraph(analysis_text, styles['Normal']),
        Paragraph(weight_text, styles['Normal'])
    ])

    # Note
    main_table_data.append([
        Paragraph('<para align="center" fontSize="8" backColor="#efefef">NOTE: Liability Limitation for loss or damage in this shipment may be applicable. See 49 U.S.C. § 14706(c)(1)(A) and (B). Non-hazardous</para>',
                  styles['Normal']), ''
    ])

    # Signatures
    shipper_text = """<para align="center">
    <b><font size="12">SHIPPER SIGNATURE</font></b><br/>
    <u><b>James Rose</b></u><br/>
    <br/>
    <font size="9">This is to certify that the above named materials are properly classified, packaged, marked and labeled, and are in proper condition for transportation according to the applicable regulations of the DOT.</font>
    </para>"""

    trailer_text = """<para align="center">
    <b>Trailer Loaded:</b><br/>
    • By Shipper<br/>
    • By Driver<br/>
    <br/>
    <b>Freight Counted:</b><br/>
    • By Shipper<br/>
    • By Driver
    </para>"""

    carrier_text = """<para align="center">
    <b><font size="12">CARRIER SIGNATURE</font></b><br/>
    <br/>
    ___________________________<br/>
    <br/>
    <font size="9">Carrier acknowledges receipt of packages and required placards. Carrier certifies emergency response information was made available and/or carrier has the DOT emergency response guidebook or equivalent documentation in the vehicle.</font>
    </para>"""

    sig_table = Table([
        [Paragraph(shipper_text, styles['Normal']),
         Paragraph(trailer_text, styles['Normal']),
         Paragraph(carrier_text, styles['Normal'])]
    ], colWidths=[2.5*inch, 2.5*inch, 2.5*inch])

    main_table_data.append([sig_table, ''])

    # Create main table
    main_table = Table(main_table_data, colWidths=[3.75*inch, 3.75*inch])

    # Apply table styles
    main_table.setStyle(TableStyle([
        # Borders
        ('BOX', (0, 0), (-1, -1), 1.5, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 1.5, colors.black),

        # Header row (SHIP FROM)
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d9d9d9')),
        ('SPAN', (0, 0), (0, 0)),  # SHIP FROM spans left
        ('SPAN', (1, 0), (-1, 0)),  # Page 1 of 1 spans right

        # Company info cell
        ('SPAN', (0, 1), (0, 1)),
        ('VALIGN', (0, 1), (0, 1), 'MIDDLE'),

        # SHIP TO bar
        ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#d9d9d9')),
        ('SPAN', (0, 2), (-1, 2)),

        # SHIP TO content
        ('SPAN', (0, 3), (-1, 3)),
        ('VALIGN', (0, 3), (-1, 3), 'MIDDLE'),

        # Product bar
        ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor('#d9d9d9')),

        # Analysis and weights row
        ('VALIGN', (0, 5), (-1, 5), 'MIDDLE'),

        # Note row
        ('BACKGROUND', (0, 6), (-1, 6), colors.HexColor('#efefef')),
        ('SPAN', (0, 6), (-1, 6)),

        # Signatures row
        ('SPAN', (0, 7), (-1, 7)),
        ('VALIGN', (0, 7), (-1, 7), 'TOP'),

        # General
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    elements.append(main_table)

    # Build PDF
    doc.build(elements)

    # Return relative path for URL
    return f'/media/bol_pdfs/{filename}'
