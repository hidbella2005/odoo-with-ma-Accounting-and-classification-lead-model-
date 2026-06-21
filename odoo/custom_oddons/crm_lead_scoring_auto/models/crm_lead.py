from odoo import models, fields, api
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)

class CrmLead(models.Model):
    _inherit = 'crm.lead'

    @api.model_create_multi
    def create(self, vals_list):
        # ──────────────────────────────────────────────────────────────────────
        # 1. ASSIGNATION DU COMMERCIAL (Avant la création en base de données)
        # ──────────────────────────────────────────────────────────────────────
        default_salesperson_id = 2  # ID de l'utilisateur de repli
        
        for vals in vals_list:
            if not vals.get('user_id'):
                # S'assurer que le default_salesperson existe toujours (en sudo)
                commercial = self.env['res.users'].sudo().browse(default_salesperson_id)
                if commercial.exists():
                    vals['user_id'] = default_salesperson_id
                    _logger.info("Assignation auto du commercial par défaut (ID: %s) pour un nouveau lead", default_salesperson_id)

        # Création effective des enregistrements dans la base de données
        leads = super(CrmLead, self).create(vals_list)

        # ──────────────────────────────────────────────────────────────────────
        # 2. LOGIQUE DE SCORING ET DE ROUTAGE (Après la création)
        # ──────────────────────────────────────────────────────────────────────
        SEUIL_CHAUD = 80
        SEUIL_TIEDE = 40
        domaines_gratuits = [
            'gmail.com', 'yahoo.com', 'yahoo.fr', 'hotmail.com', 'hotmail.fr',
            'outlook.com', 'outlook.fr', 'live.com', 'live.fr', 'aol.com',
            'icloud.com', 'mail.com', 'protonmail.com', 'gmx.com', 'gmx.fr',
            'free.fr', 'orange.fr', 'sfr.fr', 'laposte.net', 'wanadoo.fr',
            'yandex.com', 'zoho.com', 'tutanota.com',
        ]

        for lead in leads:
            score = 0
            details_score = []

            # --- Critère 1 : Revenu ---
            revenu = lead.expected_revenue or 0.0
            if revenu > 5000:
                score += 50
                details_score.append(("💰 Revenu espéré > 5 000 €", "+50", "%.2f €" % revenu))
            else:
                details_score.append(("💰 Revenu espéré ≤ 5 000 €", "+0", "%.2f €" % revenu))

            # --- Critère 2 : Email et Téléphone ---
            email_present = bool(lead.email_from and lead.email_from.strip())
            
            # Recherche d'un téléphone. "mobile" n'est pas nativement sur crm.lead mais on 
            # anticipe si un autre module l'a ajouté.
            telephone_present = bool(lead.phone and lead.phone.strip())
            if not telephone_present and hasattr(lead, 'mobile'):
                telephone_present = bool(lead.mobile and lead.mobile.strip())

            if email_present and telephone_present:
                score += 30
                details_score.append(("📧📱 Email + Téléphone", "+30", "✅ Les deux renseignés"))
            else:
                parties_manquantes = []
                if not email_present: parties_manquantes.append("email")
                if not telephone_present: parties_manquantes.append("téléphone")
                details_score.append((
                    "📧📱 Email + Téléphone", "+0",
                    "❌ Manquant : %s" % ", ".join(parties_manquantes)
                ))

            # --- Critère 3 : Domaine Email pro ---
            domaine_email = ""
            if email_present:
                email_str = lead.email_from.strip()
                if '@' in email_str:
                    domaine_email = email_str.split('@')[-1].lower().strip()
                    if domaine_email and domaine_email not in domaines_gratuits:
                        score += 20
                        details_score.append(("🏢 Domaine professionnel", "+20", "✅ @%s" % domaine_email))
                    else:
                        details_score.append(("🏢 Domaine professionnel", "+0", "❌ @%s (gratuit/personnel)" % domaine_email))
                else:
                    details_score.append(("🏢 Domaine professionnel", "+0", "❌ Format email invalide"))
            else:
                details_score.append(("🏢 Domaine professionnel", "+0", "❌ Pas d'email"))

            # --- Catégorisation ---
            if score >= SEUIL_CHAUD:
                categorie = "🔥 CHAUD"
                couleur_badge = "#e74c3c"
            elif score >= SEUIL_TIEDE:
                categorie = "🌤️ TIÈDE"
                couleur_badge = "#f39c12"
            else:
                categorie = "❄️ FROID"
                couleur_badge = "#3498db"

            _logger.info("Lead %s scoré à %s/100 → %s", lead.id, score, categorie)

            # --- Routage ---
            action_effectuee = ""
            if score >= SEUIL_CHAUD:
                # Étape Qualifié et priorité max
                stage_qualifie = self.env.ref('crm.stage_lead2', raise_if_not_found=False)
                vals_update = {'priority': '3'}
                if stage_qualifie:
                    vals_update['stage_id'] = stage_qualifie.id
                lead.write(vals_update)

                # Planification Activité "Appel" à J+1
                date_demain = fields.Date.context_today(self) + timedelta(days=1)
                try:
                    lead.activity_schedule(
                        act_type_xmlid='mail.mail_activity_data_call',
                        date_deadline=date_demain,
                        summary='🔥 Lead CHAUD — Appel de qualification prioritaire',
                        note='<p>Lead scoré à <strong>%s/100</strong>. Contacter en priorité dans les 24h.</p>' % score,
                        user_id=lead.user_id.id if lead.user_id else default_salesperson_id,
                    )
                    action_effectuee = "✅ Priorité → Très haute | Étape → Qualifié | 📞 Activité 'Appel' planifiée pour le %s" % date_demain.strftime('%d/%m/%Y')
                except Exception as e:
                    action_effectuee = "✅ Priorité → Très haute | Étape → Qualifié | ⚠️ Erreur planification activité"
                    _logger.error("Lead %s: Erreur activité - %s", lead.id, str(e))

            elif score >= SEUIL_TIEDE:
                # Étape New et nurturing
                stage_new = self.env.ref('crm.stage_lead1', raise_if_not_found=False)
                vals_update = {}
                if stage_new:
                    vals_update['stage_id'] = stage_new.id
                if vals_update:
                    lead.write(vals_update)

                lead.message_post(
                    body='<p>🌤️ <strong>Lead en phase de Nurturing</strong></p><p>Score : <strong>%s/100</strong> — Ce lead nécessite un suivi de maturation.</p>',
                    message_type='comment',
                    subtype_xmlid='mail.mt_note',
                )
                action_effectuee = "📋 Étape → En cours (New) | 📝 Note de Nurturing postée"

            else:
                # Froid: on l'archive
                lead.write({'active': False})
                action_effectuee = "🗄️ Lead archivé automatiquement (score insuffisant)"

            # --- Rapport HTML Chatter ---
            lignes_tableau = ""
            for critere, points, detail in details_score:
                lignes_tableau += (
                    '<tr>'
                    '<td style="padding:8px 12px;border-bottom:1px solid #e9ecef;">%s</td>'
                    '<td style="padding:8px 12px;border-bottom:1px solid #e9ecef;text-align:center;font-weight:bold;color:#27ae60;">%s</td>'
                    '<td style="padding:8px 12px;border-bottom:1px solid #e9ecef;">%s</td>'
                    '</tr>' % (critere, points, detail)
                )

            nom_lead = lead.name or lead.partner_name or lead.contact_name or "Sans nom"
            nom_commercial = lead.user_id.name if lead.user_id else "Non assigné"

            rapport_html = (
                '<div style="font-family:\'Segoe UI\',Roboto,sans-serif;max-width:600px;margin:10px 0;">'
                '<div style="background:linear-gradient(135deg,#667eea 0%%,#764ba2 100%%);color:white;padding:16px 20px;border-radius:8px 8px 0 0;">'
                '<h3 style="margin:0 0 4px 0;font-size:16px;">🤖 Rapport de Scoring Automatisé</h3>'
                '<p style="margin:0;opacity:0.9;font-size:13px;">Lead : %s</p>'
                '</div>'
                '<div style="background:#ffffff;border:1px solid #e9ecef;border-top:none;padding:20px;border-radius:0 0 8px 8px;">'
                '<div style="text-align:center;margin-bottom:16px;">'
                '<span style="display:inline-block;background:%s;color:white;font-size:28px;font-weight:bold;padding:12px 24px;border-radius:50px;min-width:80px;">%s / 100</span><br/>'
                '<span style="display:inline-block;margin-top:8px;padding:4px 16px;background:%s;color:white;border-radius:12px;font-size:13px;font-weight:600;">%s</span>'
                '</div>'
                '<table style="width:100%%;border-collapse:collapse;margin:16px 0;">'
                '<thead><tr style="background:#f8f9fa;">'
                '<th style="padding:8px 12px;text-align:left;font-size:13px;color:#6c757d;border-bottom:2px solid #dee2e6;">Critère</th>'
                '<th style="padding:8px 12px;text-align:center;font-size:13px;color:#6c757d;border-bottom:2px solid #dee2e6;">Points</th>'
                '<th style="padding:8px 12px;text-align:left;font-size:13px;color:#6c757d;border-bottom:2px solid #dee2e6;">Détail</th>'
                '</tr></thead>'
                '<tbody>%s</tbody>'
                '</table>'
                '<div style="background:#f0f4ff;border-left:4px solid #667eea;padding:12px 16px;margin:16px 0;border-radius:0 4px 4px 0;">'
                '<strong>👤 Commercial assigné :</strong> %s<br/>'
                '<strong>⚡ Action effectuée :</strong> %s'
                '</div>'
                '<p style="margin:12px 0 0;font-size:11px;color:#adb5bd;text-align:center;">'
                '🤖 Généré automatiquement par crm_lead_scoring_auto — %s'
                '</p></div></div>'
            ) % (
                nom_lead,
                couleur_badge, score, couleur_badge, categorie,
                lignes_tableau,
                nom_commercial,
                action_effectuee,
                fields.Datetime.now().strftime('%d/%m/%Y à %H:%M'),
            )

            # Si le lead a été archivé, il faut le réactiver temporairement pour poster un message
            lead_for_msg = lead
            was_archived = not lead.active
            
            if was_archived:
                lead_for_msg = lead.with_context(active_test=False)
                lead_for_msg.write({'active': True})

            lead_for_msg.message_post(body=rapport_html, message_type='comment', subtype_xmlid='mail.mt_note')

            if was_archived:
                lead_for_msg.write({'active': False})

        return leads
