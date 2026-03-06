#include "burnint.h"

INT32 CDEmuInit() { return 0; }
INT32 CDEmuExit() { return 0; }
INT32 CDEmuStop() { return 0; }

INT32 CDEmuPlay(UINT8, UINT8, UINT8) { return 0; }

INT32 CDEmuReadTOC(INT32) { return 0; }
INT32 CDEmuLoadSector(INT32, char*) { return 0; }
INT32 CDEmuReadQChannel() { return 0; }

INT16* CDEmuGetSoundBuffer(INT32*, INT32*) { return nullptr; }

INT32 CDEmuScan(INT32, INT32*) { return 0; }

INT32 CDEmuStatus = 0;
INT32 nCDEmuSelect = 0;
INT32 nCDEmuOffset = 0;
INT32 nCDEmuReset = 0;
