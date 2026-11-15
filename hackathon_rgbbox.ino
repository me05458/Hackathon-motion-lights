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
uint8_t col[4][3] = {{3,252,219},{255, 59, 203},{118, 255, 59},{255, 157, 59}};
int currcol = 1;
void togglecol()
{
  if(currcol = 3)
  {
    currcol = 0;
  }
  else
  {
    currcol++;
  }
}
//uint8_t col[] = {3, 252, 219};
int rad = 10;
int pos[] = {16,16};
int lastpos[] = {16,16};
float closest[] = {0.0,0.0};
float farthest[] = {0.0,0.0};

void loop() {
  if(start == 1)
  {
    /*matrix.setCursor(2,2);
  matrix.setTextColor(matrix.color565(255,255,255));
  matrix.setTextSize(1);
  matrix.setTextWrap(true);
  matrix.print("CONFIG CLOSE 4S");
  matrix.show();
  delay(4000);

  digitalWrite(trig1, LOW);
  delayMicroseconds(2);
  digitalWrite(trig1, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig1, LOW);
  duration[0] = pulseIn(echo1, HIGH);
  closest[0] = duration[0] * SOUND_SPEED/2;

  digitalWrite(trig2, LOW);
  delayMicroseconds(2);
  digitalWrite(trig2, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig2, LOW);
  duration[1] = pulseIn(echo2, HIGH);
  closest[1] = duration[1] * SOUND_SPEED/2;

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

  matrix.setCursor(2,2);
  matrix.setTextColor(matrix.color565(255,255,255));
  matrix.setTextSize(1);
  matrix.setTextWrap(true);
  matrix.print("CONFIG FAR 4S");
  matrix.show();
  delay(4000);

  digitalWrite(trig1, LOW);
  delayMicroseconds(2);
  digitalWrite(trig1, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig1, LOW);
  duration[0] = pulseIn(echo1, HIGH);
  closest[0] = duration[0] * SOUND_SPEED/2;

  digitalWrite(trig2, LOW);
  delayMicroseconds(2);
  digitalWrite(trig2, HIGH);
  delayMicroseconds(10);
  digitalWrite(trig2, LOW);
  duration[1] = pulseIn(echo2, HIGH);
  closest[1] = duration[1] * SOUND_SPEED/2;

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
  delay(1000);*/
  start = 0;
  }
  closest[0] = 12;
  closest[1] = 12;
  farthest[0] = 40;
  farthest[1] = 33;
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
  Serial.print(farthest[0]);
  Serial.print(",");
  Serial.print(farthest[1]);
  Serial.print(" | ");
  Serial.print(closest[0]);
  Serial.print(",");
  Serial.print(closest[1]);

  if(dist[0] > farthest[0])
  {
    dist[0] = farthest[0];
  }
  if(dist[0] < closest[0])
  {
    dist[0] = closest[0];
  }
  if(dist[1] > farthest[1])
  {
    dist[1] = farthest[1];
  }
  if(dist[1] < closest[1])
  {
    dist[1] = closest[1];
  }

  matrix.fillCircle(lastpos[0],lastpos[1],2,matrix.color565(0,0,0));
  lastpos[0] = pos[0];
  lastpos[1] = pos[1];

  pos[0] = (int)((31)*((float)(dist[0]-closest[0])/(farthest[0] - closest[0])));
  pos[1] = (int)(31)*((float)(dist[1]-closest[0])/(farthest[1] - closest[1]));

  Serial.print(" -------------- ");
  Serial.print(pos[0]);
  Serial.print(" | ");
  Serial.println(pos[1]);
  matrix.fillCircle(pos[0],pos[1],2,matrix.color565(col[currcol][0],col[currcol][1],col[currcol][2]));
  matrix.show();

  delay(500);
  matrix.fillScreen(matrix.color565(0,0,0));


}

