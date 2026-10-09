#pragma once
#include "acquisition_case.h"
#include <memory>

namespace disked {
// Reads only the explicitly selected store's two fixed metadata filenames.
// Never follows source/destination/map paths recorded inside the request.
// Strong pins, read-only files and fresh checks bind the immutable snapshot.
// A consistent record still does not authenticate its origin or current image.
// One owning coordinator serializes source checks; the immutable case may be
// copied/read separately without sharing these seek-based file handles.
class FileAcquisitionCase final {
    class Impl;std::unique_ptr<Impl> impl_;
public:
    FileAcquisitionCase(const std::string& operation_id,const std::string& state_directory);
    ~FileAcquisitionCase();
    FileAcquisitionCase(const FileAcquisitionCase&)=delete;FileAcquisitionCase& operator=(const FileAcquisitionCase&)=delete;
    const evidence::proposal::AcquisitionCase& report() const;
    json::Value binding() const;
    void check() const;
};
}
