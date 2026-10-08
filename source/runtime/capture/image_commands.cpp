#include "image_commands.h"
#include "map_observation.h"

namespace disked {
using json::Value;
bool image_command(const std::string& command) {return command=="image.inspect" || command=="table.verify";}
Outcome dispatch_image(const std::string& request,const std::string& command,const Value& parameters,
    const ImageCapture& capture_source,const std::string& provider) {
    if(!image_command(command))return refused(request,"command_unavailable",3);
    const auto* path=parameters.find("path"),*unit=parameters.find("logical_block_bytes");
    if(!path || path->kind!=Value::Kind::string || path->text.empty() ||
        (unit && (unit->kind!=Value::Kind::string || (unit->text!="512" && unit->text!="4096"))))
        return refused(request,"invalid_parameter");
    try {
        auto capture=capture_source(path->text,unit && unit->text=="4096"?4096:512);
        const auto& receipt=*capture.report.find("capture");
        const bool incomplete=!receipt.find("regions_complete")->boolean || !receipt.find("reread_regions_complete")->boolean;
        const bool changed=!receipt.find("metadata_equal")->boolean || !receipt.find("overlap_equal")->boolean ||
            (!incomplete && !receipt.find("reread_equal")->boolean);
        auto result=Value::object().put("schema",Value::string("org.disked.raw-image-observation/1"))
            .put("command",Value::string(command)).put("provider",Value::string(provider))
            .put("scope",Value::string("ordinary-local-raw-file")).put("map",std::move(capture.report));
        auto out=completed(request,std::move(result));
        if(incomplete || changed) {
            out.exit_code=4;out.response.put("status",Value::string("failed"));
            if(incomplete)out.response.fields["diagnostics"].items.push_back(diagnostic("image_capture_incomplete"));
            if(changed)out.response.fields["diagnostics"].items.push_back(diagnostic("image_source_changed"));
        }
        // The complete region manifest is bound by the receipt digest. Its
        // retrieval/export is not admitted by this bounded command projection.
        json::dump(out.response);return out;
    } catch(const ImageCaptureError& error) {
        auto out=refused(request,error.what(),3);
        if(error.platform_code)out.response.fields["diagnostics"].items.front().put("platform_code",Value::string(std::to_string(error.platform_code)));
        return out;
    } catch(const MapObservationError& error) {return refused(request,error.what(),3);}
    catch(const json::Error&) {return refused(request,"image_report_limit",3);}
    catch(const std::exception&) {return refused(request,"internal_error",4);}
}
}
