#pragma once
#include "runtime/planner/gpt_repair.h"
#include "map_observation.h"

namespace disked {
// Private bounded region selection over a supplied reader. No file or effect I/O.
planner::proposal::GptRepairCapture capture_gpt_regions(const std::string& image_id,
    std::uint64_t epoch,std::uint64_t blocks,std::uint32_t block_bytes,const MapRegionReader& reader);
}
