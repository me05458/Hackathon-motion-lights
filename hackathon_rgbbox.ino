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
  if(status!= PROTOMATTER_OK)
  {
    for(;;); //catastrophic faliure oh no
  }
  
}
uint8_t boardcol[] = {0,0,0};
int pos[] = {16,16};
void loop() {

  drawCircles(16,16,255,0,0);
  drawCircles(0,0,0,0,255);
  drawCircles(20,20,0,255,0);

    /*for(int i = 0; i<32;i++)
    {
      for(int j = 0; j<32; j++)
      {
        matrix.drawPixel(i,j,matrix.color565(7*(uint8_t)i,7*(uint8_t)j,255));
      }
    }
    matrix.show();*/

}

void fix(int* r, int* g, int* b)
{
  /*if(&r<0)
  {
    r = 0;
  }
  if(&r>255)
  {
    r = 255;
  }
  if(&g<0)
  {
    g = 0;
  }
  if(g>255)
  {
    g = 255;
  }
  if(b<0)
  {
    b = 0;
  }
  if(b>255)
  {
    b = 255;
  }*/
}

int max(int a, int b)
{
  if(a > b)
  {
    return a;
  }
  return b;
}

void drawCircles(int x, int y, int newr, int newb, int newg)
{
  if(x < 0 || y < 0 || x >=32 || y >=32)
  {
    Serial.println("invalid x,y");
    return;
  }
  fix(&newr,&newb,&newg);
  int mult[] = {1,1,1};
  if(boardcol[0] > newr)
  {
    mult[0] = -1;
  }
  if(boardcol[1] > newg)
  {
    mult[1] = -1;
  }
  if(boardcol[2] > newb)
  {
    mult[2] = -1;
  }
  //magic number = 4
  int stepr = (((mult[0]*newr)-(boardcol[0]*mult[0]))/4);
  int stepg = (((mult[1]*newg)-(boardcol[1]*mult[1]))/4);
  int stepb = (((mult[2]*newb)-(boardcol[2]*mult[2]))/4);
  for(int levels = 1; levels<=4; levels++)
  {
    int tmpr = boardcol[0]+(mult[0]*stepr*levels)+1;
    int tmpg = boardcol[0]+(mult[0]*stepg*levels)+1;
    int tmpb = boardcol[0]+(mult[0]*stepb*levels)+1;
    fix(&tmpr,&tmpg,&tmpb);
    for(int rad = 0; rad<46; rad++)
    {
      matrix.fillCircle(x,y,rad,matrix.color565((uint8_t)tmpr,(uint8_t)tmpg,(uint8_t)tmpb));
      matrix.show();
      delay(100);
    }
  }
}
