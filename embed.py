pseudocode
// ============================================
// SMART HOME ROOM CONTROLLER STATE MACHINE
// ============================================

// GLOBAL STATE VARIABLES
enum SystemMode { NORMAL, AWAY, ALARM }
SystemMode currentMode = NORMAL

// Sensor state variables
bool motionDetected = false
bool doorOpen = false
float currentTemp = 22.0
int smokeLevel = 0
bool afterSunset = false
bool validDisarmCode = false

// Actuator state variables
bool hvacHeatOn = false
bool hvacCoolOn = false
int fanPWM = 0              // 0-255 (0-100%)
int ledStripPWM = 0         // 0-255
bool strikeEngaged = false
bool sirenActive = false

// Timing variables
unsigned long lightTimer = 0
unsigned long sirenTimer = 0
unsigned long lastTempChange = 0

// Hysteresis constants
const float TEMP_HEAT_ON = 20.0      // 21°C - 1°C hysteresis
const float TEMP_HEAT_OFF = 21.0
const float TEMP_COOL_ON = 26.0      // 25°C + 1°C hysteresis
const float TEMP_COOL_OFF = 25.0
const float TEMP_COMFORT_LOW = 21.0
const float TEMP_COMFORT_HIGH = 25.0

// Timing constants
const unsigned long LIGHT_DURATION = 180000  // 3 minutes in ms
const unsigned long SIREN_DURATION = 30000   // 30 seconds in ms

// ============================================
// MAIN CONTROL LOOP
// ============================================
void mainControlLoop() {
while (true) {
// Read all sensors
readAllSensors()

// PRIORITY 1: Smoke detection (highest priority)
if (smokeLevel >= 328) {  // 1.6V threshold
handleSmokeAlarm()
            continue  // Skip other logic during smoke emergency
}

// PRIORITY 2: Security system state machine
switch (currentMode) {
            case NORMAL:
handleNormalMode()
break

            case AWAY:
handleAwayMode()
break

            case ALARM:
handleAlarmMode()
break
}

delay(50)  // 20Hz control loop
}
}

// ============================================
// SENSOR READING
// ============================================
void readAllSensors() {
// Read digital sensors
motionDetected = digitalRead(PIR_PIN)
doorOpen = !digitalRead(REED_PIN)  // Active low with pull-up

// Read temperature with averaging
int tempADC = readADC(TEMP_ADC_CHANNEL)
float voltage = tempADC * 4.8828 / 1000.0  // Convert to volts
    currentTemp = (voltage - 0.5) * 100.0      // TMP36 conversion

// Read smoke level
smokeLevel = readADC(SMOKE_ADC_CHANNEL)

// Read humidity via I²C (implementation specific)
float humidity = readI2CHumidity()

// Determine day/night state (could use RTC or light sensor)
afterSunset = checkTimeAfterSunset()
}

// ============================================
// NORMAL MODE HANDLER
// ============================================
void handleNormalMode() {
// === TEMPERATURE CONTROL WITH HYSTERESIS ===
// Hysteresis prevents rapid cycling (chattering)

if (currentTemp <= TEMP_HEAT_ON) {
// Too cold - activate heating
if (!hvacHeatOn) {
hvacHeatOn = true
hvacCoolOn = false
fanPWM = 0
setHVAC(HEAT)
lastTempChange = millis()
}
}
else if (currentTemp >= TEMP_HEAT_OFF && currentTemp < TEMP_COMFORT_LOW) {
// Hysteresis band - maintain previous state if heating
// This prevents oscillation at threshold boundary
}
else if (currentTemp >= TEMP_COMFORT_LOW && currentTemp <= TEMP_COMFORT_HIGH) {
// Comfortable range - no heating/cooling, gentle circulation
hvacHeatOn = false
hvacCoolOn = false
fanPWM = 77  // 30% circulation (77/255)
setHVAC(OFF)
setFanPWM(fanPWM)
}
else if (currentTemp > TEMP_COMFORT_HIGH && currentTemp < TEMP_COOL_ON) {
// Hysteresis band - maintain previous state if cooling
}
else if (currentTemp >= TEMP_COOL_ON) {
// Too hot - activate cooling
if (!hvacCoolOn) {
hvacHeatOn = false
hvacCoolOn = true
fanPWM = 204  // 80% PWM (204/255)
setHVAC(COOL)
setFanPWM(fanPWM)
lastTempChange = millis()
}
}

// === LIGHTING CONTROL ===
if ((motionDetected || doorOpen) && afterSunset) {
// Trigger or extend light timer
lightTimer = millis()
ledStripPWM = 153  // 60% brightness (153/255)
setLEDStrip(ledStripPWM)
}
else if (millis() - lightTimer > LIGHT_DURATION) {
// Timer expired - turn off lights
ledStripPWM = 0
setLEDStrip(0)
}
// Motion extends timer automatically by resetting lightTimer above

// === SECURITY STATE TRANSITION ===
// Check if user arms the system
if (checkArmCommand()) {
        currentMode = AWAY
strikeEngaged = true
setElectronicStrike(ENGAGED)
logEvent("System armed - Away mode")
}
}

// ============================================
// AWAY MODE HANDLER
// ============================================
void handleAwayMode() {
// Temperature control continues in background (same as normal)
handleTemperatureControl()

// === INTRUSION DETECTION ===
if (doorOpen || motionDetected) {
// Intrusion detected!
        currentMode = ALARM
sirenTimer = millis()
sirenActive = true
strikeEngaged = true  // Ensure door stays locked

setElectronicStrike(ENGAGED)
setSiren(ON)

// Send alert notification via Wi-Fi
sendUARTAlert("INTRUSION DETECTED")

logEvent("ALARM: Intrusion detected in Away mode")
}

// Check for disarm command
if (checkDisarmCode()) {
        currentMode = NORMAL
strikeEngaged = false
setElectronicStrike(DISENGAGED)
logEvent("System disarmed - Normal mode")
}
}

// ============================================
// ALARM MODE HANDLER
// ============================================
void handleAlarmMode() {
// Maintain alarm state
strikeEngaged = true
setElectronicStrike(ENGAGED)

// Check siren duration
if (millis() - sirenTimer > SIREN_DURATION) {
// 30 seconds elapsed - silence siren but maintain alarm state
sirenActive = false
setSiren(OFF)
logEvent("Siren timeout - maintaining alarm state")
}

// === CHECK FOR VALID DISARM CODE ===
if (checkValidDisarmCode()) {
// User entered correct code - cancel alarm
        currentMode = NORMAL
sirenActive = false
strikeEngaged = false

setSiren(OFF)
setElectronicStrike(DISENGAGED)

logEvent("Alarm disarmed - Valid code received")
}

// Alarm remains active until valid disarm
// Temperature control suspended during alarm (safety priority)
}

// ============================================
// SMOKE EMERGENCY HANDLER (Highest Priority)
// ============================================
void handleSmokeAlarm() {
// Override all other functions - life safety priority

// Shut down HVAC to prevent smoke circulation
hvacHeatOn = false
hvacCoolOn = false
setHVAC(OFF)

// Turn on all lights for visibility
ledStripPWM = 255  // 100% brightness
setLEDStrip(255)

// Unlock door for emergency egress
strikeEngaged = false
setElectronicStrike(DISENGAGED)

// Activate siren with distinct pattern
activateSmokeAlarmPattern()

// Send emergency alert
sendUARTAlert("FIRE/SMOKE EMERGENCY")

logEvent("CRITICAL: Smoke detected - emergency mode")

// Remain in emergency state until manual reset
// (smoke level check would continue in main loop)
}

// ============================================
// PRIORITY CONFLICT RESOLUTION
// ============================================
/*
PRIORITY HIERARCHY (highest to lowest):
1. SMOKE ALARM - Overrides everything, life safety critical
2. SECURITY ALARM - Prevents intrusion, property protection
3. TEMPERATURE CONTROL - Comfort and equipment protection
4. LIGHTING CONTROL - Convenience feature

CONFLICT EXAMPLES:
- If smoke detected during away mode: Smoke handler runs,
door unlocks for egress despite security concerns

- If door opens in away mode: Alarm triggers, overriding
normal lighting control

- Temperature hysteresis: Prevents conflicts between heating
and cooling by introducing dead band

TIMING CONFLICTS:
- Light timer extends on motion, not resets (prevents
flickering when motion is intermittent)

- Siren has 30s timeout to prevent indefinite noise, but
alarm state persists requiring explicit disarm
*/

// ============================================
// HELPER FUNCTIONS
// ============================================

void setHVAC(enum HVACMode mode) {
// Control relay through optocoupler/MOSFET
    digitalWrite(HVAC_HEAT_PIN, mode == HEAT ? HIGH : LOW)
    digitalWrite(HVAC_COOL_PIN, mode == COOL ? HIGH : LOW)
}

void setFanPWM(int pwmValue) {
// PWM output through MOSFET driver
analogWrite(FAN_PWM_PIN, pwmValue)  // 0-255
}

void setLEDStrip(int pwmValue) {
analogWrite(LED_PWM_PIN, pwmValue)
}

void setElectronicStrike(bool engaged) {
// Engaged = locked, Disengaged = unlocked
    digitalWrite(STRIKE_PIN, engaged ? HIGH : LOW)
}

void setSiren(bool active) {
    digitalWrite(SIREN_PIN, active ? HIGH : LOW)
}

bool checkValidDisarmCode() {
// Read UART for disarm code transmission
    if (Serial.available() >= 4) {
        char code[5];
        Serial.readBytes(code, 4)
        code[4] = '\0'
return (strcmp(code, "1234") == 0)  // Example code
}
return false
}

void sendUARTAlert(const char* message) {
// Send alert to Wi-Fi module via UART
    Serial.print("ALERT:");
    Serial.println(message)
}

