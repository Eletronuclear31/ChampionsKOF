#pragma once

#include <cstdint>
#include <vector>

struct FrameData
{
    uint64_t frameNumber = 0;
    uint32_t inputMask = 0;
    uint64_t stateHash = 0;

    std::vector<uint8_t> snapshot; // será usado quando integrarmos FBNeo
};
