"""
Professional BOL PDF Generation using ReportLab
Designed for black & white laser printers
"""
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
import os
from io import BytesIO
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile


def generate_bol_pdf(bol_data, output_path=None):
    """
    Generate a professional BOL PDF

    Args:
        bol_data: BOL model object or dictionary with BOL data
        output_path: Optional custom output path

    Returns:
        The file path
    """
    # Handle both model objects and dictionaries
    if hasattr(bol_data, '__dict__') and not isinstance(bol_data, dict):
        # It's a model object
        data = bol_data
    else:
        # It's a dictionary, create attribute-style accessor
        class DictWrapper:
            def __init__(self, d):
                self._data = d
            def __getattr__(self, key):
                if key == 'bol_number':
                    return self._data.get('bolNumber') or self._data.get('bol_number', 'PREVIEW')
                elif key == 'customer_po':
                    return self._data.get('customerPO') or self._data.get('customer_po', '')
                elif key == 'carrier_name':
                    return self._data.get('carrierName') or self._data.get('carrier_name', '')
                elif key == 'truck_number':
                    return self._data.get('truckNumber') or self._data.get('truck_number', '')
                elif key == 'trailer_number':
                    return self._data.get('trailerNumber') or self._data.get('trailer_number', '')
                elif key == 'buyer_name':
                    return self._data.get('buyerName') or self._data.get('buyer_name', '')
                elif key == 'ship_to':
                    return self._data.get('shipTo') or self._data.get('ship_to', '')
                elif key == 'product_name':
                    return self._data.get('productName') or self._data.get('product_name', '')
                elif key == 'net_tons':
                    return self._data.get('netTons') or self._data.get('net_tons', 0)
                elif key == 'date':
                    return self._data.get('date', '')
                elif key == 'release_number':
                    return self._data.get('releaseNumber') or self._data.get('release_number', '')
                elif key == 'lot_ref':
                    return self._data.get('lot_ref') or self._data.get('lotRef', None)
                elif key == 'special_instructions':
                    return self._data.get('specialInstructions') or self._data.get('special_instructions', '')
                return self._data.get(key, '')
        data = DictWrapper(bol_data)

    # Generate PDF to memory buffer (works with both S3 and local storage)
    buffer = BytesIO()

    # Create PDF in landscape for more space
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),  # 11" wide x 8.5" tall
        rightMargin=0.3*inch,
        leftMargin=0.3*inch,
        topMargin=0.3*inch,
        bottomMargin=0.3*inch
    )

    elements = []
    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'BOLTitle',
        parent=styles['Heading1'],
        fontSize=20,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        spaceAfter=4
    )

    header_style = ParagraphStyle(
        'Header',
        parent=styles['Normal'],
        fontSize=8,
        fontName='Helvetica-Bold'
    )

    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=8
    )

    # ========== HEADER SECTION ==========
    # Load logos
    cbrt_logo_path = os.path.join(settings.BASE_DIR, 'static', 'cbrt-logo.jpg')
    prime_logo_path = os.path.join(settings.BASE_DIR, 'static', 'primetrade-logo.jpg')

    cbrt_logo = None
    prime_logo = None

    # Format date
    try:
        date_obj = datetime.strptime(data.date, '%Y-%m-%d')
        formatted_date = date_obj.strftime('%m/%d/%Y')
    except:
        formatted_date = data.date

    # Header table: No logos - clean and simple
    header_data = [[
        # Left: BILL OF LADING title
        Paragraph('<b>BILL OF LADING</b>', title_style),

        # Right: BOL Number
        Paragraph(f'<para align="right"><font size="7">BOL NUMBER</font><br/><b><font size="14">{data.bol_number}</font></b></para>', normal_style),
    ]]

    header_table = Table(header_data, colWidths=[6.0*inch, 4.0*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    elements.append(header_table)

    # Horizontal line
    line_table = Table([['']], colWidths=[10*inch], rowHeights=[0.02*inch])
    line_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.black),
    ]))
    elements.append(line_table)
    elements.append(Spacer(1, 0.02*inch))

    # ========== MAIN INFO SECTION (TWO COLUMNS) ==========
    # Get dynamic data
    lot_number = ''
    chemistry_text = 'N/A'

    if hasattr(data, 'lot_ref') and data.lot_ref:
        lot = data.lot_ref
        lot_number = lot.code

        # Build chemistry string
        chem_parts = []
        if lot.c is not None:
            chem_parts.append(f'C {float(lot.c):.3f}%')
        if lot.si is not None:
            chem_parts.append(f'Si {float(lot.si):.3f}%')
        if lot.s is not None:
            chem_parts.append(f'S {float(lot.s):.3f}%')
        if lot.p is not None:
            chem_parts.append(f'P {float(lot.p):.3f}%')
        if lot.mn is not None:
            chem_parts.append(f'Mn {float(lot.mn):.3f}%')

        if chem_parts:
            chemistry_text = ' | '.join(chem_parts)

    release_num = ''
    if hasattr(data, 'release_number') and data.release_number:
        release_num = data.release_number

    # Calculate weights (short tons: 2000 lbs/ton)
    total_weight_lbs = int(float(data.net_tons) * 2000) if data.net_tons else 0
    net_tons = float(data.net_tons) if data.net_tons else 0

    # Left column: Ship From + Consignee
    # Get c/o company from BOL data (defaults to PrimeTrade, LLC for backward compatibility)
    co_company = getattr(data, 'care_of_co', None) or 'PrimeTrade, LLC'

    left_col_data = [
        [Paragraph('<b>SHIP FROM:</b>', header_style)],
        [Paragraph(f'<b>Cincinnati Barge & Rail Terminal, LLC</b><br/>c/o {co_company}<br/>1707 Riverside Drive<br/>Cincinnati, Ohio 45202<br/>Phone: (513) 721-1707', normal_style)],
        [Spacer(1, 0.05*inch)],
        [Paragraph('<b>CONSIGNEE (SHIP TO):</b>', header_style)],
        [Paragraph(f'<b>{data.buyer_name}</b><br/><font size="7">{data.ship_to.replace(chr(10), "<br/>")}</font>', normal_style)]
    ]

    left_col_table = Table(left_col_data, colWidths=[4.5*inch])
    left_col_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#E0E0E0')),
        ('BACKGROUND', (0, 3), (0, 3), colors.HexColor('#E0E0E0')),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))

    # Right column: Shipment details
    right_col_data = [
        [Paragraph('<b>SHIPMENT INFORMATION</b>', header_style)],
        [Table([
            [Paragraph('<b>Date:</b>', normal_style), Paragraph(formatted_date, normal_style)],
            [Paragraph('<b>Customer PO#:</b>', normal_style), Paragraph(data.customer_po or '', normal_style)],
            [Paragraph('<b>Release #:</b>', normal_style), Paragraph(release_num, normal_style)],
            [Paragraph('<b>Carrier:</b>', normal_style), Paragraph(data.carrier_name, normal_style)],
            [Paragraph('<b>Truck #:</b>', normal_style), Paragraph(data.truck_number, normal_style)],
            [Paragraph('<b>Trailer #:</b>', normal_style), Paragraph(data.trailer_number, normal_style)],
        ], colWidths=[1.2*inch, 3*inch], style=TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))]
    ]

    right_col_table = Table(right_col_data, colWidths=[4.5*inch])
    right_col_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#E0E0E0')),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))

    # Combine left and right columns
    main_info_table = Table([[left_col_table, right_col_table]], colWidths=[4.7*inch, 4.7*inch])
    main_info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))

    elements.append(main_info_table)
    elements.append(Spacer(1, 0.03*inch))

    # ========== MATERIAL/PRODUCT SECTION ==========
    material_data = [[
        Paragraph(f'<b>MATERIAL DESCRIPTION</b>', header_style),
        Paragraph(f'<b>LOT NUMBER</b>', header_style),
        Paragraph(f'<b>WEIGHT</b>', header_style)
    ]]

    material_data.append([
        Paragraph(f'<b>{data.product_name}</b><br/><font size="8">Analysis: {chemistry_text}</font>', normal_style),
        Paragraph(f'<para align="center"><b>{lot_number or "N/A"}</b></para>', normal_style),
        Paragraph(f'<para align="center"><b>{total_weight_lbs:,} LBS</b><br/><b>{net_tons:.2f} N.T.</b></para>', normal_style)
    ])

    material_table = Table(material_data, colWidths=[5*inch, 2*inch, 2.4*inch])
    material_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E0E0E0')),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))

    elements.append(material_table)
    elements.append(Spacer(1, 0.02*inch))

    # ========== NOTES/DISCLAIMER SECTION ==========
    notes_text = '<b>IMPORTANT NOTES:</b><br/>'
    notes_text += '• Weights referenced are estimates. See scale ticket for actual weight.<br/>'
    notes_text += '• Liability Limitation for loss or damage in this shipment may be applicable. See 49 U.S.C. § 14706(c)(1)(A) and (B).<br/>'
    notes_text += '• Material is non-hazardous.<br/>'
    notes_text += '• This is to certify that the above named materials are properly classified, packaged, marked and labeled, and are in proper condition for transportation according to the applicable regulations of the DOT.'

    notes_table = Table([[Paragraph(notes_text, ParagraphStyle('Notes', parent=normal_style, fontSize=8, leading=10))]], colWidths=[9.4*inch])
    notes_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F5F5F5')),
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))

    elements.append(notes_table)
    elements.append(Spacer(1, 0.03*inch))

    # ========== CRITICAL DELIVERY INSTRUCTIONS ==========
    # Display prominently if present
    if hasattr(data, 'special_instructions') and data.special_instructions:
        special = data.special_instructions.strip()
        if special:
            # Replace newlines with <br/> for proper rendering
            special = special.replace('\n', '<br/>')

            # Create prominent alert-style box for critical instructions
            critical_style = ParagraphStyle(
                'Critical',
                parent=normal_style,
                fontSize=12,
                leading=16,
                textColor=colors.HexColor('#8B0000'),  # Dark red
                alignment=1  # Center
            )

            critical_text = f'<b>⚠ CRITICAL DELIVERY INSTRUCTION ⚠</b><br/><br/>{special}'
            critical_table = Table([[Paragraph(critical_text, critical_style)]], colWidths=[9.4*inch])
            critical_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FFF4E6')),  # Light orange/yellow
                ('BOX', (0, 0), (-1, -1), 3, colors.HexColor('#FF6B00')),  # Thick orange border
                ('TOPPADDING', (0, 0), (-1, -1), 12),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('LEFTPADDING', (0, 0), (-1, -1), 12),
                ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ]))

            elements.append(critical_table)
            elements.append(Spacer(1, 0.02*inch))

    # ========== SIGNATURE SECTION ==========
    sig_data = [[
        Paragraph('<b>SHIPPER SIGNATURE</b><br/><br/>_____________________________<br/>James Rose<br/><font size="7">Authorized Representative</font>', normal_style),
        Paragraph('<b>CARRIER SIGNATURE</b><br/><br/>_____________________________<br/>Driver Name<br/><font size="7">Date / Time</font>', normal_style)
    ]]

    sig_table = Table(sig_data, colWidths=[4.7*inch, 4.7*inch])
    sig_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))

    elements.append(sig_table)

    # Build PDF
    doc.build(elements)

    # If output_path is provided (for preview mode), save to local file
    if output_path:
        buffer.seek(0)
        with open(output_path, 'wb') as f:
            f.write(buffer.read())
        return output_path

    # Otherwise, save to storage (S3 in production, local filesystem in development)
    buffer.seek(0)

    # Organize by year for better file management
    try:
        date_obj = datetime.strptime(data.date, '%Y-%m-%d')
        year = date_obj.year
    except:
        year = datetime.now().year

    # Generate file path: bols/YYYY/PRT-YYYY-NNNN.pdf
    filename = f"bols/{year}/{data.bol_number}.pdf"

    # Save using Django storage backend (automatically uses S3 or filesystem)
    saved_path = default_storage.save(filename, ContentFile(buffer.read()))

    # Return URL (automatically generates signed URL if using S3)
    return default_storage.url(saved_path)
