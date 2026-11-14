#include <Adafruit_Protomatter.h>


uint8_t rgbPins[]  = {16, 17, 18, 19, 27, 14};
uint8_t addrPins[] = {33, 26, 32, 25};
uint8_t clockPin   = 21;
uint8_t latchPin   = 15;
uint8_t oePin      = 5;
ProtomatterStatus status;
Adafruit_Protomatter matrix(32, 5, 1, rgbPins, 4, addrPins, clockPin, latchPin, oePin, true);
void setup() {
  Serial.begin(115200);
  status = matrix.begin();

  
}
void loop() {
  if(status == PROTOMATTER_OK)
  {
    //matrix.drawCircle(12, 10, 9, matrix.color565(255, 0, 0));
    //delay(100);
    for(int i = 16; i<32; i++)
    {
      matrix.drawPixel(i,16,matrix.color565(255,255,0));
      matrix.show();
      delay(100);
      matrix.drawPixel(i,16,matrix.color565(0,0,0));
    }
    for(int i = 31; i>=0; i--)
    {
      matrix.drawPixel(i,16,matrix.color565(0,255,255));
       matrix.show();
      delay(100);
      matrix.drawPixel(i,16,matrix.color565(0,0,0));
    }
    for(int i = 1; i<=16; i++)
    {
      matrix.drawPixel(i,16,matrix.color565(255,0,255));
       matrix.show();
      delay(100);
      matrix.drawPixel(i,16,matrix.color565(0,0,0));
    }
    for(int i = 16; i<32; i++)
    {
      matrix.drawPixel(16,i,matrix.color565(0,255,0));
       matrix.show();
      delay(100);
      matrix.drawPixel(16,i,matrix.color565(0,0,0));
    }
    for(int i = 31; i>=0; i--)
    {
      matrix.drawPixel(16,i,matrix.color565(255,0,0));
       matrix.show();
      delay(100);
      matrix.drawPixel(16,i,matrix.color565(0,0,0));
    }
    for(int i = 1; i<=16; i++)
    {
      matrix.drawPixel(16,i,matrix.color565(0,0,255));
       matrix.show();
      delay(100);
      matrix.drawPixel(16,i,matrix.color565(0,0,0));
    }
  }
  else
  {
    Serial.println("FALIURE");
    if(status == PROTOMATTER_ERR_PINS)
    {
      Serial.println("Pins error");
    }
    else if(status == PROTOMATTER_ERR_MALLOC)
    {
      Serial.println("Malloc error :)");
    }
    else if(status == PROTOMATTER_ERR_ARG)
    {
      Serial.println("Rare error oh no panic");
    }
    else
    {
      Serial.println("More rare error oh no panic more");
    }
    return;
  }
}

void drawCircles(int x, int y)
{
  
}
