from flask import Blueprint, jsonify, request
from app.database import get_db
from app.decorators import role_required

venues_bp = Blueprint(
    "venues",
    __name__,
    url_prefix="/api/venues"
)


def validate_venue_data(data, partial=False):
    if not isinstance(data, dict) or not data:
        return None, "A valid JSON object is required."

    allowed = {"venue_name", "location", "capacity"}

    if not set(data).issubset(allowed):
        return None, "Invalid venue fields."

    if not partial and not allowed.issubset(data):
        return None, "Venue name, location and capacity are required."

    result = {}

    for field in ("venue_name", "location"):
        if field in data:
            value = data[field]

            if not isinstance(value, str) or not value.strip():
                return None, f"{field} must be non-empty text."

            result[field] = value.strip()

    if "capacity" in data:
        value = data["capacity"]

        if isinstance(value, bool):
            return None, "Capacity must be a positive integer."

        try:
            capacity = int(value)
        except (ValueError, TypeError):
            return None, "Capacity must be a positive integer."

        if capacity <= 0 or str(capacity) != str(value).strip():
            return None, "Capacity must be a positive integer."

        result["capacity"] = capacity

    return result, None


@venues_bp.route("/", methods=["GET"])
@role_required("admin")
def get_venues():
    db = get_db()

    venues = db.execute("""
        SELECT venue_id, venue_name, location, capacity
        FROM venues
        ORDER BY venue_name
    """).fetchall()

    return jsonify({
        "venues": [dict(venue) for venue in venues],
        "count": len(venues)
    }), 200


@venues_bp.route("/", methods=["POST"])
@role_required("admin")
def create_venue():
    data, error = validate_venue_data(
        request.get_json(silent=True)
    )

    if error:
        return jsonify({"error": error}), 400

    db = get_db()

    try:
        cursor = db.execute("""
            INSERT INTO venues (venue_name, location, capacity)
            VALUES (?, ?, ?)
        """, (
            data["venue_name"],
            data["location"],
            data["capacity"]
        ))

        db.commit()

        return jsonify({
            "message": "Venue created successfully.",
            "venue_id": cursor.lastrowid
        }), 201

    except Exception as exc:
        db.rollback()

        if "UNIQUE constraint failed" in str(exc):
            return jsonify({
                "error": "A venue with this name already exists."
            }), 409

        raise


@venues_bp.route("/<int:venue_id>", methods=["GET"])
@role_required("admin")
def get_venue(venue_id):
    db = get_db()

    venue = db.execute("""
        SELECT venue_id, venue_name, location, capacity
        FROM venues
        WHERE venue_id = ?
    """, (venue_id,)).fetchone()

    if venue is None:
        return jsonify({"error": "Venue not found."}), 404

    return jsonify({"venue": dict(venue)}), 200


@venues_bp.route("/<int:venue_id>", methods=["PUT"])
@role_required("admin")
def update_venue(venue_id):
    data, error = validate_venue_data(
        request.get_json(silent=True),
        partial=True
    )

    if error:
        return jsonify({"error": error}), 400

    db = get_db()

    venue = db.execute("""
        SELECT venue_id, venue_name, location, capacity
        FROM venues
        WHERE venue_id = ?
    """, (venue_id,)).fetchone()

    if venue is None:
        return jsonify({"error": "Venue not found."}), 404

    updated = dict(venue)
    updated.update(data)

    if "capacity" in data:
        largest_event = db.execute("""
            SELECT MAX(capacity) AS largest_capacity
            FROM events
            WHERE venue_id = ?
              AND status IN ('pending', 'approved')
        """, (venue_id,)).fetchone()["largest_capacity"]

        if largest_event and updated["capacity"] < largest_event:
            return jsonify({
                "error": "Venue capacity cannot be lower than an existing event capacity."
            }), 409

    try:
        db.execute("""
            UPDATE venues
            SET venue_name = ?, location = ?, capacity = ?
            WHERE venue_id = ?
        """, (
            updated["venue_name"],
            updated["location"],
            updated["capacity"],
            venue_id
        ))

        db.commit()

        return jsonify({
            "message": "Venue updated successfully.",
            "venue_id": venue_id
        }), 200

    except Exception as exc:
        db.rollback()

        if "UNIQUE constraint failed" in str(exc):
            return jsonify({
                "error": "A venue with this name already exists."
            }), 409

        raise


@venues_bp.route("/<int:venue_id>", methods=["DELETE"])
@role_required("admin")
def delete_venue(venue_id):
    db = get_db()

    venue = db.execute("""
        SELECT venue_id FROM venues
        WHERE venue_id = ?
    """, (venue_id,)).fetchone()

    if venue is None:
        return jsonify({"error": "Venue not found."}), 404

    event_count = db.execute("""
        SELECT COUNT(*) AS total
        FROM events
        WHERE venue_id = ?
    """, (venue_id,)).fetchone()["total"]

    if event_count:
        return jsonify({
            "error": "This venue cannot be deleted because events are associated with it."
        }), 409

    db.execute("""
        DELETE FROM venues
        WHERE venue_id = ?
    """, (venue_id,))

    db.commit()

    return jsonify({
        "message": "Venue deleted successfully."
    }), 200