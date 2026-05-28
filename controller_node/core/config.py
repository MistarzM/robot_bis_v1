import math

# ============================================================================
# NETWORKING
# ============================================================================

# EXTERNAL NETWORK (Wi-Fi: Laptop <-> Raspberry Pi)
ZMQ_CONTROL_PORT  = "5555"
ZMQ_VIDEO_PORT    = "5556"
ZMQ_FEEDBACK_PORT = "5557"

# INTERNAL NETWORK (Localhost: Inside Raspberry Pi)
ZMQ_LOCAL_COMMANDS  = "5558"
ZMQ_LOCAL_TELEMETRY = "5559"


# ============================================================================
# ARM
# ============================================================================

ARM_PORT = '/dev/ttyUSB0'
ARM_BAUD = 115200

SPEED_LINEAR  = 2.0
SPEED_ANGULAR = 0.02
MAX_STEP      = 16
GRIP_SPEED    = 10

# Arm link dimensions (mm)
A1 = 52.0
A2 = 50.5
A3 = 150.0
A4 = 51.0
A5 = 88.5
A6 = 179.0
MAX_REACH = A2 + A3 + A5 + A6 - 5.0


# ----------------------------------------------------------------------------
# Joint identity — single source of truth
# ----------------------------------------------------------------------------
# Used by the GUI, telemetry parsers, and logging. Names MUST match the
# firmware's AxisProfile table in esp32_arm_bridge.ino.
JOINT_NAMES = {
    0: "Base",
    1: "Shoulder L",
    2: "Shoulder R",
    3: "Elbow",
    4: "Forearm Roll",
    5: "Wrist Pitch",
    6: "Wrist Roll",
    7: "Gripper",
}


# ----------------------------------------------------------------------------
# Hardware calibration
# ----------------------------------------------------------------------------

SERVO_MIN = 0
SERVO_MAX = 4095
SHOULDER_CALIB_ANGLE_DEG = 90.0

CALIB_BASE = 2048

# ── Dual-drive shoulder (J2) ────────────────────────────────────────────────
# IDs 1 and 2 drive the SAME mechanical joint. Their horns can never be
# attached perfectly aligned — there's typically a few raw units (≈ one
# spline tooth ≈ 8 raw) of mechanical offset between them. Calibrate each
# motor INDEPENDENTLY so you can compensate that offset in software:
#
#   1. Power on with torque enabled, command home (ELBOW_DOWN_POS).
#   2. Look at the joint. If it's slightly fighting / one motor is
#      pre-loaded, nudge CALIB_SHOULDER_R by ±1..±10 raw units until
#      the joint sits relaxed.
#
# Default below assumes a symmetric mount (no offset). Change either value
# independently as needed — DO NOT keep them derived from each other.
CALIB_SHOULDER_L = 1985
CALIB_SHOULDER_R = SERVO_MAX - CALIB_SHOULDER_L   # = 2110 with no offset.
                                                  # e.g. 2115 to add +5 raw
                                                  # units of offset on R.
# ────────────────────────────────────────────────────────────────────────────

CALIB_ELBOW        = 2400
CALIB_FOREARM_ROLL = 2148
CALIB_WRIST_PITCH  = 2300
CALIB_WRIST_ROLL   = 2048
CALIB_GRIPPER      = 2848


# ----------------------------------------------------------------------------
# Pose presets (raw servo counts per ID)
# ----------------------------------------------------------------------------

# "Elbow Down" home — physical resting pose used at boot and on HOMING.
ELBOW_DOWN_POS = {
    0: CALIB_BASE,
    1: CALIB_SHOULDER_L,
    2: CALIB_SHOULDER_R,          # independent of L so horn offset is preserved
    3: CALIB_ELBOW,
    4: CALIB_FOREARM_ROLL,
    5: CALIB_WRIST_PITCH,
    6: CALIB_WRIST_ROLL,
    7: CALIB_GRIPPER,
}

# Mathematical "zero" pose for the IK chain (arm fully extended along +X).
# Note: ID 2 is intentionally absent — the dual-drive shoulder has a single
# logical DOF and is driven from ID 1 via the mirror in arm_service.py.
ZERO_POS = {
    0: CALIB_BASE,
    1: CALIB_SHOULDER_L - int(SHOULDER_CALIB_ANGLE_DEG / 0.088),
    3: CALIB_ELBOW,
    4: CALIB_FOREARM_ROLL,
    5: CALIB_WRIST_PITCH,
    6: CALIB_WRIST_ROLL,
    7: CALIB_GRIPPER,
}


# ----------------------------------------------------------------------------
# Joint software limits (raw counts, inclusive)
# ----------------------------------------------------------------------------
# ID 2 (Shoulder R) inherits its limits from ID 1 via the mirror — do not
# add it here independently.
JOINT_LIMITS = {
    0: (0,    4095),   # Base          — full range
    1: (1150, 3350),   # Shoulder L
    3: (1300, 3300),   # Elbow
    4: (0,    4095),   # Forearm Roll  — full range
    5: (1250, 3350),   # Wrist Pitch
    6: (0,    4095),   # Wrist Roll    — full range
    7: (1900, 3850),   # Gripper
}


# ============================================================================
# CHASSIS
# ============================================================================

CHASSIS_PORT       = '/dev/ttyACM0'
CHASSIS_BAUD       = 115200
CHASSIS_MAX_SPEED  = 0.2
CHASSIS_ACCEL_STEP = 0.01
CHASSIS_DECEL_STEP = 0.05
