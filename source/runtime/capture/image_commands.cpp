#include "image_commands.h"
#include "map_observation.h"

namespace disked {
using json::Value;
bool image_command(const std::string& command) {return command=="image.inspect" || command=="table.verify" || command=="table.gpt.repair.plan";}
Outcome dispatch_image(const std::string& request,const std::string& command,const Value& parameters,
    const ImageCapture& capture_source,const std::string& provider,const FatInspectionPort& fat, FatCaptureStore *store, const ExfatInspectionPort& exfat, const NtfsInspectionPort& ntfs) {
    if(!image_command(command))return refused(request,"command_unavailable",3);
    if(command=="image.inspect" && fat_inspection_parameters(parameters))return dispatch_fat_inspection(request,parameters,fat,store);
    if(command=="image.inspect" && exfat_inspection_parameters(parameters))return dispatch_exfat_inspection(request,parameters,exfat);
    if(command=="image.inspect" && ntfs_inspection_parameters(parameters))return dispatch_ntfs_inspection(request,parameters,ntfs);
    if(parameters.find("retain_capture"))return refused(request,"invalid_parameter",2);
    const auto* path=parameters.find("path"),*unit=parameters.find("logical_block_bytes");
    if(!path || path->kind!=Value::Kind::string || path->text.empty() ||
        (unit && (unit->kind!=Value::Kind::string || (unit->text!="512" && unit->text!="4096"))))
        return refused(request,"invalid_parameter");
    const bool repair=command=="table.gpt.repair.plan";
    const auto* source=parameters.find("authoritative_copy"),*decision=parameters.find("selection_decision_digest");
    if(repair && (!source || source->kind!=Value::Kind::string || (source->text!="primary" && source->text!="backup") ||
        (decision && (decision->kind!=Value::Kind::string || decision->text.size()!=71 || decision->text.compare(0,7,"sha256:") ||
        decision->text.find_first_not_of("0123456789abcdef",7)!=std::string::npos || decision->text.substr(7)==std::string(64,'0')))))
        return refused(request,"invalid_parameter");
    try {
        auto capture=capture_source(path->text,unit && unit->text=="4096"?4096:512,repair);
        const auto& receipt=*capture.report.find("capture");
        const bool incomplete=!receipt.find("regions_complete")->boolean || !receipt.find("reread_regions_complete")->boolean;
        const bool changed=!receipt.find("metadata_equal")->boolean || !receipt.find("overlap_equal")->boolean ||
            (!incomplete && !receipt.find("reread_equal")->boolean);
        auto result=Value::object().put("schema",Value::string(repair?"org.disked.gpt-repair-command-result/1":"org.disked.raw-image-observation/1"))
            .put("command",Value::string(command)).put("provider",Value::string(provider))
            .put("scope",Value::string("ordinary-local-raw-file"));
        if(repair) {
            result.put("profile",Value::string("ordinary-local-gpt-repair-preview/1")).put("capture",receipt).put("plan_digest",Value{}).put("definition",Value{});
            if(!incomplete && !changed) {
                if(!capture.repair_captured)throw ImageCaptureError("image_region_contract");
                planner::proposal::GptRepairSelection selection;selection.source=source->text=="primary"?planner::proposal::GptCopy::primary:planner::proposal::GptCopy::backup;
                if(decision)selection.decision_digest=decision->text;
                const planner::proposal::GptRepairPlan plan(capture.repair,capture.repair_digest,selection);
                result.put("plan_digest",Value::string(plan.digest())).put("definition",plan.definition());
            }
        } else result.put("map",std::move(capture.report));
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
    } catch(const planner::proposal::RepairError& error) {return refused(request,error.what(),3);
    } catch(const MapObservationError& error) {return refused(request,error.what(),3);}
    catch(const json::Error&) {return refused(request,"image_report_limit",3);}
    catch(const std::exception&) {return refused(request,"internal_error",4);}
}
}
