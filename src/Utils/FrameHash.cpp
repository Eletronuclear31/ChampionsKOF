#include "FrameHash.h"

uint64_t FrameHash::compute(uint64_t frameNumber, uint32_t inputMask)
{
    uint64_t hash = 1469598103934665603ULL; // FNV offset basis

    hash ^= frameNumber;
    hash *= 1099511628211ULL;

    hash ^= inputMask;
    hash *= 1099511628211ULL;

    return hash;
}
