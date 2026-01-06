"""
BOL Creation Service.

Centralized BOL creation with tenant validation and atomic state transitions.
"""
from django.db import transaction
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class BOLCreationService:
    """
    Centralized BOL creation.

    Responsibilities:
    - Tenant boundary validation
    - Atomic ReleaseLoad status update
    - Snapshot population
    - PDF generation trigger (future)
    """

    @staticmethod
    @transaction.atomic
    def create_bol(
        release_line,
        carrier,
        truck,
        net_tons,
        issued_by='',
    ):
        """
        Create BOL for a ReleaseLoad (ReleaseLine in spec).

        Validates tenant boundaries, locks ReleaseLoad, creates BOL,
        updates status, all in single transaction.

        Args:
            release_line: ReleaseLoad instance (the load being shipped)
            carrier: Carrier instance
            truck: Truck instance (optional)
            net_tons: Decimal weight in tons
            issued_by: Email of user creating the BOL

        Returns:
            BOL instance

        Raises:
            ValueError: If validation fails (tenant mismatch, wrong status, etc.)
        """
        from ..models import BOL, BOLCounter, ReleaseLoad

        tenant = release_line.tenant
        release = release_line.release

        # Lock ReleaseLoad to prevent concurrent BOL creation
        release_line = ReleaseLoad.objects.select_for_update().get(
            pk=release_line.pk
        )

        # Validate ReleaseLoad is PENDING
        if release_line.status != 'PENDING':
            raise ValueError(
                f"ReleaseLoad {release_line.pk} is {release_line.status}, not PENDING"
            )

        # Tenant boundary validation - explicit checks
        if carrier.tenant_id and carrier.tenant_id != tenant.id:
            raise ValueError(
                f"Carrier tenant mismatch: carrier belongs to tenant {carrier.tenant_id}, "
                f"expected {tenant.id}"
            )
        if truck and truck.carrier.tenant_id and truck.carrier.tenant_id != tenant.id:
            raise ValueError(
                f"Truck carrier tenant mismatch: truck's carrier belongs to tenant "
                f"{truck.carrier.tenant_id}, expected {tenant.id}"
            )

        lot = release.lot_ref
        if lot and lot.tenant_id and lot.tenant_id != tenant.id:
            raise ValueError(
                f"Lot tenant mismatch: lot belongs to tenant {lot.tenant_id}, "
                f"expected {tenant.id}"
            )

        # Get next BOL number - use tenant config for prefix if available
        prefix = 'PRT'  # Default for PrimeTrade
        bol_number = BOLCounter.get_next_bol_number(tenant, prefix)

        # Format ship-to address
        ship_to_parts = []
        if release.ship_to_name:
            ship_to_parts.append(release.ship_to_name)
        if release.ship_to_street:
            ship_to_parts.append(release.ship_to_street)
        if release.ship_to_street2:
            ship_to_parts.append(release.ship_to_street2)
        city_state_zip = []
        if release.ship_to_city:
            city_state_zip.append(release.ship_to_city)
        if release.ship_to_state:
            city_state_zip.append(release.ship_to_state)
        if release.ship_to_zip:
            city_state_zip.append(release.ship_to_zip)
        if city_state_zip:
            ship_to_parts.append(', '.join(city_state_zip[:2]) + ' ' + (city_state_zip[2] if len(city_state_zip) > 2 else ''))
        ship_to_address = '\n'.join(ship_to_parts)

        # Get buyer name from customer ref or text
        buyer_name = ''
        if release.customer_ref:
            buyer_name = release.customer_ref.customer
        elif release.customer_id_text:
            buyer_name = release.customer_id_text

        # Create BOL with all snapshots
        bol = BOL.objects.create(
            tenant=tenant,
            bol_number=bol_number,
            bol_date=timezone.now().date(),
            date=timezone.now().strftime('%Y-%m-%d'),  # Legacy field
            issued_by=issued_by,
            created_by_email=issued_by,  # Legacy field

            # Canonical relationships
            release_line=release_line,
            lot=lot,
            product=release.lot_ref.product if release.lot_ref and release.lot_ref.product else None,
            customer=release.customer_ref,
            carrier=carrier,
            truck=truck,

            # Snapshot display fields
            release_display=f"{release.release_number}-{release_line.seq}",
            product_name=release.material_description or (release.lot_ref.product.name if release.lot_ref and release.lot_ref.product else ''),
            buyer_name=buyer_name,
            carrier_name=carrier.carrier_name,
            truck_number=truck.truck_number if truck else '',
            trailer_number=truck.trailer_number if truck else '',
            chemistry_display=lot.format_chemistry() if lot else '',

            # Address and instructions (snapshot)
            ship_to=ship_to_address,
            customer_po=release.customer_po,
            special_instructions=release.special_instructions,
            care_of_co=release.care_of_co,
            release_number=release.release_number,  # Legacy field

            # Weight
            net_tons=net_tons,

            # Legacy lot ref
            lot_ref=lot,
        )

        # Update ReleaseLoad status
        release_line.status = 'SHIPPED'
        release_line.shipped_at = timezone.now()
        release_line.bol = bol  # Legacy FK
        release_line.save()

        # Check if all loads shipped → mark Release COMPLETE
        pending_count = release.loads.filter(status='PENDING').count()
        if pending_count == 0:
            release.status = 'COMPLETE'
            release.save()

        logger.info(
            f"Created BOL {bol_number} for ReleaseLoad {release_line.pk} "
            f"(Release {release.release_number}-{release_line.seq}) by {issued_by}"
        )

        return bol

    @staticmethod
    @transaction.atomic
    def void_bol(bol, voided_by, reason):
        """
        Void a BOL and revert ReleaseLoad to PENDING.

        Args:
            bol: BOL instance to void
            voided_by: Email of user voiding the BOL
            reason: Reason for voiding

        Returns:
            BOL instance (now voided)

        Raises:
            ValueError: If BOL already voided
        """
        if bol.is_void:
            raise ValueError(f"BOL {bol.bol_number} already voided")

        bol.is_void = True
        bol.voided_at = timezone.now()
        bol.voided_by = voided_by
        bol.void_reason = reason
        bol.save()

        # Revert ReleaseLoad if linked
        release_line = bol.release_line
        if release_line:
            release_line.status = 'PENDING'
            release_line.shipped_at = None
            release_line.bol = None  # Legacy FK
            release_line.save()

            # Revert Release if needed
            release = release_line.release
            if release.status == 'COMPLETE':
                release.status = 'OPEN'
                release.save()

        logger.info(
            f"Voided BOL {bol.bol_number} by {voided_by}: {reason}"
        )

        return bol

    @staticmethod
    def update_official_weight(bol, weight_tons, entered_by_email):
        """
        Update official weight on BOL.

        Delegates to BOL.set_official_weight for variance calculation
        and stamped PDF generation.

        Args:
            bol: BOL instance
            weight_tons: Official weight in tons
            entered_by_email: Email of user entering weight

        Returns:
            BOL instance
        """
        bol.set_official_weight(weight_tons, entered_by_email)
        logger.info(
            f"Updated official weight for BOL {bol.bol_number}: "
            f"{weight_tons} tons by {entered_by_email}"
        )
        return bol
