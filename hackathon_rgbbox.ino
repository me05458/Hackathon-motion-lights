#include <Adafruit_Protomatter.h>

const int trig1 = 13;
const int echo1 = 12;
const int trig2 = 4;
const int echo2 = 2;
uint8_t rgbPins[]  = {16, 17, 18, 19, 27, 14};
uint8_t addrPins[] = {33, 26, 32, 25};
uint8_t clockPin   = 21;
uint8_t latchPin   = 15;
uint8_t oePin      = 5;

#define SOUND_SPEED 0.034

ProtomatterStatus status;
Adafruit_Protomatter matrix(32, 5, 1, rgbPins, 4, addrPins, clockPin, latchPin, oePin, true);
float initdist[] = {0.0,0.0};
long duration[] = {0,0};
float dist[] = {0.0,0.0};
int start = 1;
void setup() {
  Serial.begin(115200);
  status = matrix.begin();
  pinMode(trig1, OUTPUT); // Sets the trigPin as an Output
  pinMode(echo2, INPUT); // Sets the echoPin as an Input
  pinMode(trig2, OUTPUT); // Sets the trigPin as an Output
  pinMode(echo1, INPUT); // Sets the echoPin as an Input
  if(status!= PROTOMATTER_OK)
  {
    for(;;); //catastrophic faliure oh no
  }

  

}
uint8_t col[] = {100,0,0};
int rad = 10;
int pos[] = {16,16};

void loop() {
  if(start == 1)
  {
    matrix.setCursor(2,2);
  matrix.setTextColor(matrix.color565(255,255,255));
  matrix.setTextSize(1);
  matrix.setTextWrap(true);
  matrix.print("CONFIG IN 4 SEC");
  matrix.show();
  delay(4000);

  digitalWrite(trig1, LOW);
  delayMicroseconds(2);
  digitalWrite(trig1, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig1, LOW);
  duration[0] = pulseIn(echo1, HIGH);
  initdist[0] = duration[0] * SOUND_SPEED/2;

  digitalWrite(trig2, LOW);
  delayMicroseconds(2);
  digitalWrite(trig2, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig2, LOW);
  duration[1] = pulseIn(echo2, HIGH);
  initdist[1] = duration[1] * SOUND_SPEED/2;

  matrix.fillScreen(matrix.color565(0,0,0));
  matrix.setCursor(2,2);
  matrix.setTextColor(matrix.color565(255,255,255));
  matrix.setTextSize(1);
  matrix.setTextWrap(true);
  matrix.print("DONE");
  matrix.show();
  Serial.println("---");
  Serial.println(initdist[0]);
  Serial.println(initdist[1]);
  Serial.println("---");
  delay(1000);
  start = 0;
  }
  digitalWrite(trig1, LOW);
  delayMicroseconds(2);
  digitalWrite(trig1, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig1, LOW);
  duration[0] = pulseIn(echo1, HIGH);
  dist[0] = duration[0] * SOUND_SPEED/2;
  digitalWrite(trig2, LOW);
  delayMicroseconds(2);
  digitalWrite(trig2, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig2, LOW);
  duration[1] = pulseIn(echo2, HIGH);
  dist[1] = duration[1] * SOUND_SPEED/2;
  Serial.print(dist[0]);
  Serial.print(" | ");
  Serial.print(dist[1]);
  Serial.print(" -------------- ");
  Serial.print((dist[0] - initdist[0]));
  Serial.print(" | ");
  Serial.println((dist[1] - initdist[1]));

  rad = 10+(dist[0] - initdist[0]);
  if(dist[1] - initdist[1] >= 0)
  {
    col[2] = (dist[1] - initdist[1])*10;
  }
  else
  {
    col[1] = (initdist[1] - dist[1])*10;
  }

  matrix.fillCircle(16,16,rad,matrix.color565(col[0],col[1],col[2]));
  matrix.show();

  delay(100);
  matrix.fillScreen(matrix.color565(0,0,0));


}

