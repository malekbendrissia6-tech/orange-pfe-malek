"""Export conversation chatbot en PDF — necessite reportlab."""
from io import BytesIO
from datetime import datetime

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.colors import HexColor
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.enums import TA_CENTER
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False


class PDFExporter:

    def export_conversation(self, conversation: dict, messages: list, user_info: dict) -> BytesIO:
        if not REPORTLAB_OK:
            raise RuntimeError("reportlab non installe. Lancez : pip install reportlab")

        ORANGE = HexColor('#FF6600')
        GRIS   = HexColor('#666666')
        NOIR   = HexColor('#000000')

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            rightMargin=2*cm, leftMargin=2*cm,
            topMargin=2*cm, bottomMargin=2*cm,
        )
        styles = getSampleStyleSheet()

        title_s = ParagraphStyle('OTitle', parent=styles['Title'],
                                 textColor=ORANGE, fontSize=22,
                                 spaceAfter=8, alignment=TA_CENTER)
        sub_s   = ParagraphStyle('OSub', parent=styles['Normal'],
                                 textColor=GRIS, fontSize=11,
                                 spaceAfter=16, alignment=TA_CENTER)
        meta_s  = ParagraphStyle('OMeta', parent=styles['Normal'],
                                 textColor=GRIS, fontSize=9, spaceAfter=4)
        user_s  = ParagraphStyle('OUser', parent=styles['Normal'],
                                 textColor=NOIR, fontSize=11,
                                 leftIndent=8, spaceAfter=6,
                                 backColor=HexColor('#F5F5F5'), borderPadding=6)
        asst_s  = ParagraphStyle('OAsst', parent=styles['Normal'],
                                 textColor=NOIR, fontSize=11,
                                 leftIndent=8, spaceAfter=10,
                                 backColor=HexColor('#FFF5EE'), borderPadding=6)

        story = [
            Paragraph('Orange Tunisie', title_s),
            Paragraph('Conversation — Assistant Intelligent', sub_s),
            Paragraph(f"<b>Utilisateur :</b> {user_info.get('nom_complet', 'N/A')}", meta_s),
            Paragraph(f"<b>Date :</b> {datetime.now().strftime('%d/%m/%Y a %H:%M')}", meta_s),
            Paragraph(f"<b>Sujet :</b> {conversation.get('titre', 'Conversation')}", meta_s),
            Spacer(1, 0.5*cm),
        ]

        for msg in messages:
            role    = msg.get('role', '')
            content = msg.get('content', '')
            if role == 'user':
                story.append(Paragraph(f"<b>Vous :</b> {content}", user_s))
            elif role == 'assistant':
                story.append(Paragraph(f"<b>Assistant :</b> {content}", asst_s))

        story += [
            Spacer(1, 1*cm),
            Paragraph('<i>Document genere par la Plateforme Orange Tunisie</i>', meta_s),
            Paragraph('<i>PFE Malek Ben Drissia — ESB Tunisie 2026</i>', meta_s),
        ]

        doc.build(story)
        buffer.seek(0)
        return buffer
