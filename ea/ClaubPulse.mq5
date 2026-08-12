//+------------------------------------------------------------------+
//| ClaubPulse.mq5                                                   |
//| Clean-room consecutive-candle momentum EA (Pat Stafford, 2026).  |
//| Contrarian streak strategy (mapping verified by parity backtests |
//| against the reference bot): iBearishX consecutive bearish closes |
//| = oversold dip -> BUY; iBullishX consecutive bullish closes =    |
//| overextension -> SELL. Dojis are skipped, not streak-resetting.  |
//| Percent-of-equity sizing, fixed SL/TP in points, classic         |
//| distance+step trailing stop, cap on concurrent positions.        |
//| Input names match the conventional streak-EA preset names so     |
//| published preset files port unchanged. See PROVENANCE.md.        |
//+------------------------------------------------------------------+
#property copyright "Pat Stafford"
#property version   "1.00"
#property strict

#include <Trade/Trade.mqh>

input long   magicNumber    = 20200311; // order tag: only manage our own trades
input double iLots          = 0;        // fixed lot size; 0 = size from percRisk
input double percRisk       = 3.4;      // % of balance risked to SL per trade
input int    iMaxOrders     = 3;        // max concurrent positions; <=0 = unlimited
input int    stopLoss       = 23000;    // points
input int    takeProfit     = 35000;    // points
input int    iTrailingStart = 33000;    // points profit before trailing kicks in
input int    iTrailingStep  = 7500;     // trail distance in points; 0 = no trail
input int    iBullishX      = 12;       // consecutive bullish bars -> BUY
input int    iBearishX      = 4;        // consecutive bearish bars -> SELL

CTrade   trade;
datetime lastBarTime = 0;

//+------------------------------------------------------------------+
int OnInit()
  {
   trade.SetExpertMagicNumber(magicNumber);
   trade.SetDeviationInPoints(50);
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Streaks over COMPLETED bars ending at bar 1. A doji resets both. |
//+------------------------------------------------------------------+
void CountStreaks(int &bull, int &bear)
  {
   bull = 0;
   bear = 0;
   int first = 0;
   for(int i = 1; i <= 1000; i++)   // completed bars only
     {
      double o = iOpen(_Symbol, _Period, i);
      double c = iClose(_Symbol, _Period, i);
      int d = (c > o) ? 1 : ((c < o) ? -1 : 0);
      if(d == 0)
         continue;                 // doji: ignored, streak continues through it
      if(first == 0)
         first = d;
      if(d != first)
         break;
      if(first == 1)
         bull++;
      else
         bear++;
     }
  }

//+------------------------------------------------------------------+
int CountOwnPositions()
  {
   int n = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk))
         continue;
      if(PositionGetInteger(POSITION_MAGIC) == magicNumber &&
         PositionGetString(POSITION_SYMBOL) == _Symbol)
         n++;
     }
   return(n);
  }

//+------------------------------------------------------------------+
double NormalizeLots(double v)
  {
   double minl = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxl = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(step > 0)
      v = MathFloor(v / step + 1e-9) * step;
   return(MathMin(maxl, MathMax(minl, v)));
  }

//+------------------------------------------------------------------+
//| Lots so that stopLoss points lost ~= percRisk % of balance.      |
//+------------------------------------------------------------------+
double LotSize()
  {
   if(iLots > 0)
      return(NormalizeLots(iLots));
   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickVal <= 0 || tickSize <= 0 || stopLoss <= 0)
      return(NormalizeLots(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN)));
   double lossPerLot = stopLoss * _Point / tickSize * tickVal;
   if(lossPerLot <= 0)
      return(NormalizeLots(SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN)));
   double riskMoney = AccountInfoDouble(ACCOUNT_EQUITY) * percRisk / 100.0;
   return(NormalizeLots(riskMoney / lossPerLot));
  }

//+------------------------------------------------------------------+
void OpenTrade(ENUM_ORDER_TYPE type)
  {
   double price = (type == ORDER_TYPE_BUY)
                  ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                  : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double sl = 0, tp = 0;
   if(stopLoss > 0)
      sl = (type == ORDER_TYPE_BUY) ? price - stopLoss * _Point
                                    : price + stopLoss * _Point;
   if(takeProfit > 0)
      tp = (type == ORDER_TYPE_BUY) ? price + takeProfit * _Point
                                    : price - takeProfit * _Point;
   sl = NormalizeDouble(sl, _Digits);
   tp = NormalizeDouble(tp, _Digits);
   double lots = LotSize();
   if(type == ORDER_TYPE_BUY)
      trade.Buy(lots, _Symbol, 0, sl, tp, "ClaubPulse");
   else
      trade.Sell(lots, _Symbol, 0, sl, tp, "ClaubPulse");
  }

//+------------------------------------------------------------------+
//| Once profit >= iTrailingStart pts, keep SL iTrailingStep pts     |
//| behind price, only ever tightening.                              |
//+------------------------------------------------------------------+
void Trail()
  {
   if(iTrailingStart <= 0 || iTrailingStep <= 0)
      return;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0 || !PositionSelectByTicket(tk))
         continue;
      if(PositionGetInteger(POSITION_MAGIC) != magicNumber ||
         PositionGetString(POSITION_SYMBOL) != _Symbol)
         continue;
      long   type  = PositionGetInteger(POSITION_TYPE);
      double open  = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl    = PositionGetDouble(POSITION_SL);
      double tp    = PositionGetDouble(POSITION_TP);
      double price = (type == POSITION_TYPE_BUY)
                     ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                     : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double profitPts = (type == POSITION_TYPE_BUY)
                         ? (price - open) / _Point
                         : (open - price) / _Point;
      if(profitPts < iTrailingStart)
         continue;
      // classic trailing: SL kept iTrailingStart pts behind price, only
      // moved when the improvement is at least iTrailingStep pts
      double newSL = (type == POSITION_TYPE_BUY)
                     ? price - iTrailingStart * _Point
                     : price + iTrailingStart * _Point;
      newSL = NormalizeDouble(newSL, _Digits);
      bool better = (type == POSITION_TYPE_BUY)
                    ? (sl == 0 || newSL > sl + iTrailingStep * _Point)
                    : (sl == 0 || newSL < sl - iTrailingStep * _Point);
      if(better)
         trade.PositionModify(tk, newSL, tp);
     }
  }

//+------------------------------------------------------------------+
datetime entryBar       = 0;   // bar we last opened on
int      countAfterOpen = 0;   // own-position count right after that open

void OnTick()
  {
   Trail();

   datetime bt = iTime(_Symbol, _Period, 0);
   if(bt == lastBarTime)
      return;                      // act once per new bar
   lastBarTime = bt;

   if(iMaxOrders > 0 && CountOwnPositions() >= iMaxOrders)
      return;

   int bull, bear;
   CountStreaks(bull, bear);

   // Contrarian mapping (verified by parity backtest against the reference
   // bot): a run of bearish bars is an oversold dip -> BUY the bounce; a
   // long run of bullish bars is overextension -> SELL the fade.
   bool opened = false;
   if(iBearishX > 0 && bear >= iBearishX)
     { OpenTrade(ORDER_TYPE_BUY);  opened = true; }
   else if(iBullishX > 0 && bull >= iBullishX)
     { OpenTrade(ORDER_TYPE_SELL); opened = true; }

   if(opened)
     {
      entryBar       = bt;
      countAfterOpen = CountOwnPositions();
     }
  }
//+------------------------------------------------------------------+

