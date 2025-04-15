import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { CheckCircle, XCircle, Clock, ExternalLink, AlertCircle, Hash, Server, Cpu, Database, HardDrive } from "lucide-react"
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog"
import { useEffect, useState } from "react"

// Custom VisuallyHidden component instead of importing from Radix UI
const VisuallyHidden = ({ children }) => (
  <div 
    style={{
      border: 0,
      clip: 'rect(0 0 0 0)',
      height: '1px',
      margin: '-1px',
      overflow: 'hidden',
      padding: 0,
      position: 'absolute',
      width: '1px',
      whiteSpace: 'nowrap',
      wordWrap: 'normal'
    }}
  >
    {children}
  </div>
);

export default function CustomProgressBar() {
  // Use state to track if props have been received
  const [hasProps, setHasProps] = useState(false);
  
  // Use effect to check if props are received later
  useEffect(() => {
    // Log props for debugging
    console.log("CustomProgressBar props received:", props);
    
    // Check if we have meaningful props
    if (props && (props.title || props.value !== undefined || props.completedLinks)) {
      setHasProps(true);
      console.log("Valid props detected:", props);
    }
  }, [props]);
  
  // Create safe versions of all props with defaults
  const safeProps = {
    value: props?.value || 0,
    title: props?.title || "Task Progress",
    progressName: props?.progressName || "Completed 0/0",
    details: props?.details || { total: 0, done: 0, failed: 0, pending: 0 },
    completedLinks: Array.isArray(props?.completedLinks) ? props?.completedLinks : [],
    list_failed: Array.isArray(props?.list_failed) ? props?.list_failed : []
  };
  
  // Determine agent type based on title
  const agentType = safeProps.title?.includes("RC") ? "RC" : 
                   safeProps.title?.includes("RE") ? "RE" : "RX";
  
  console.log(`CustomProgressBar rendering with agentType: ${agentType}, hasProps: ${hasProps}`);
  
  const renderTaskItem = (item, index) => {
    // If item is null or undefined, return a fallback message
    if (!item) {
      return (
        <div className="flex flex-col">
          <div className="flex items-center mb-1">
            <span className="text-gray-500">No data available</span>
          </div>
        </div>
      );
    }
    
    switch(agentType) {
      case "RC":
        // RC task format (resource monitoring)
        console.log('Rendering RC task item:', item);
        return (
          <div className="flex flex-col">
            <div className="flex items-start mb-1">
              <Server className="h-3 w-3 mr-1 flex-shrink-0 mt-0.5 text-blue-500" />
              <span className="text-blue-600 font-medium">{item.data || "Resource data unavailable"}</span>
            </div>
            <div className="flex justify-between text-gray-500 text-[10px] mt-1">
              <span className="flex items-center">
                <Hash className="h-2.5 w-2.5 mr-1" />
                Task: {(item.task_id || item.id || "Unknown").substring(0, 8)}
              </span>
              <span>Agent: {(item.agent_id || "Unknown").split('-')[0]}</span>
            </div>
          </div>
        );
      
      case "RE":
        // RE task format (if implemented in the future)
        return (
          <div className="flex flex-col">
            <div className="flex items-start mb-1">
              <Database className="h-3 w-3 mr-1 flex-shrink-0 mt-0.5 text-purple-500" />
              <span className="text-purple-600 font-medium">{item.data || "Task completed"}</span>
            </div>
            <div className="flex justify-between text-gray-500 text-[10px] mt-1">
              <span className="flex items-center">
                <Hash className="h-2.5 w-2.5 mr-1" />
                Task: {item.task_id?.substring(0, 8) || "N/A"}
              </span>
              <span>Agent: {item.agent_id?.split('-')[0] || "N/A"}</span>
            </div>
          </div>
        );
      
      case "RX":
      default:
        // For RX tasks, the item itself is a URL string
        if (typeof item === 'string') {
          return (
            <div className="flex flex-col">
              <div className="flex items-center mb-1">
                <a 
                  href={item} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  className="flex items-center"
                >
                  <ExternalLink className="h-3 w-3 mr-1 flex-shrink-0 mt-0.5 text-blue-500" />
                  <span className="break-all">{item}</span>
                </a>
              </div>
            </div>
          );
        } else {
          // Handle case where RX data is in object format
          return (
            <div className="flex flex-col">
              <div className="flex items-center mb-1">
                <ExternalLink className="h-3 w-3 mr-1 flex-shrink-0 mt-0.5 text-blue-500" />
                <span className="break-all">{item.data || "Task completed"}</span>
              </div>
            </div>
          );
        }
    }
  };
  
  const renderFailedItem = (item, index) => {
    console.log('Rendering failed item:', item);
    return (
      <div className="flex flex-col">
        <span className="font-semibold text-red-600 mb-1">{item.error || "Unknown error"}</span>
        <div className="flex justify-between text-gray-500">
          <span>Task ID: {item.task_id || "N/A"}</span>
          <span>
            {agentType === "RX" ? "X ID:" : "Agent ID:"}
            {" "}
            {agentType === "RX" ? item.x_id : (item.id || "Unknown")}
          </span>
        </div>
      </div>
    );
  };
  
  const getTaskTitle = () => {
    switch(agentType) {
      case "RC": return "Completed Resource Monitoring:";
      case "RE": return "Completed Task Results:";
      case "RX": 
      default: return "Completed Post Tasks:";
    }
  };
  
  return (
    <Card className="w-full max-w-md">
      <CardHeader className="pb-2">
        <div className="flex justify-between items-center">
          <CardTitle className="text-lg font-medium">
            {safeProps.title}
          </CardTitle>
          {safeProps.value > 0 && (
            <Badge variant={safeProps.value >= 100 ? "success" : "default"} className="ml-2">
              {safeProps.value}%
            </Badge>
          )}
        </div>
      </CardHeader>

      <CardContent>
        <div className="space-y-4">
          {/* Progress bar section */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">
                {safeProps.progressName}
              </span>
            </div>
            <Progress value={safeProps.value} className="h-2" />
          </div>
          
          {/* Task statistics section */}
          <div className="grid grid-cols-3 gap-2 bg-muted/50 p-2 rounded-md">
            <div className="flex flex-col items-center">
              <div className="flex items-center text-xs text-muted-foreground mb-1">
                <CheckCircle className="h-3 w-3 mr-1 text-green-500" />
                <span>Done</span>
              </div>
              <span className="font-semibold">{safeProps.details?.done || 0}</span>
            </div>
            
            <div className="flex flex-col items-center">
              <div className="flex items-center text-xs text-muted-foreground mb-1">
                <XCircle className="h-3 w-3 mr-1 text-red-500" />
                <span>Failed</span>
              </div>
              <span className="font-semibold">{safeProps.details?.failed || 0}</span>
            </div>
            
            <div className="flex flex-col items-center">
              <div className="flex items-center text-xs text-muted-foreground mb-1">
                <Clock className="h-3 w-3 mr-1 text-amber-500" />
                <span>Pending</span>
              </div>
              <span className="font-semibold">{safeProps.details?.pending || 0}</span>
            </div>
          </div>
          
          {/* Total tasks section */}
          <div className="flex justify-between text-sm px-1">
            <span className="font-medium">Total Tasks:</span>
            <span className="font-semibold">{safeProps.details?.total || 0}</span>
          </div>
          
          {/* Task results section - only show if there are completed tasks */}
          {safeProps.completedLinks.length > 0 && (
            <div className="mt-4">
              <h4 className="text-sm font-semibold mb-2 flex items-center">
                <CheckCircle className="h-3 w-3 mr-1 text-green-500" />
                {getTaskTitle()}
              </h4>
              <div className="max-h-48 overflow-y-auto bg-muted/30 rounded-md p-2">
                <ul className="space-y-2">
                  {safeProps.completedLinks.map((item, index) => (
                    <li key={index} className="text-xs bg-white p-2 rounded shadow-sm border border-green-100">
                      {renderTaskItem(item, index)}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
          
          {/* Failed tasks section - only show if there are failed tasks */}
          {safeProps.list_failed.length > 0 && (
            <div className="mt-4">
              <h4 className="text-sm font-semibold mb-2 text-red-500 flex items-center">
                <AlertCircle className="h-3 w-3 mr-1" />
                Failed Tasks:
              </h4>
              <div className="max-h-48 overflow-y-auto bg-red-50 rounded-md p-2 border border-red-200">
                <ul className="space-y-2">
                  {safeProps.list_failed.map((item, index) => (
                    <li key={index} className="text-xs bg-white p-2 rounded shadow-sm border border-red-100">
                      {renderFailedItem(item, index)}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
          
          {/* Fix for Dialog accessibility warning */}
          <Dialog>
            <DialogContent>
              <VisuallyHidden>
                <DialogTitle>Task Progress Details</DialogTitle>
              </VisuallyHidden>
              {/* Dialog content would go here */}
            </DialogContent>
          </Dialog>
        </div>
      </CardContent>
    </Card>
  );
}


// import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
// import { Badge } from "@/components/ui/badge"
// import { Progress } from "@/components/ui/progress"
// import { CheckCircle, XCircle, Clock, ExternalLink, AlertCircle } from "lucide-react"

// export default function CustomProgressBar(props) {
//   return (
//     <Card className="w-full max-w-md">
//       <CardHeader className="pb-2">
//         <div className="flex justify-between items-center">
//           <CardTitle className="text-lg font-medium">
//             {props.title || "Jobs to do"}
//           </CardTitle>
//           {props.value > 0 && (
//             <Badge variant={props.value >= 100 ? "success" : "default"} className="ml-2">
//               {props.value}%
//             </Badge>
//           )}
//         </div>
//       </CardHeader>

//       <CardContent>
//         <div className="space-y-4">
//           {/* Progress bar section */}
//           <div className="space-y-2">
//             <div className="flex items-center justify-between">
//               <span className="text-sm font-medium">
//                 {props.progressName}
//               </span>
//             </div>
//             <Progress value={props.value || 0} className="h-2" />
//           </div>
          
//           {/* Task statistics section */}
//           <div className="grid grid-cols-3 gap-2 bg-muted/50 p-2 rounded-md">
//             <div className="flex flex-col items-center">
//               <div className="flex items-center text-xs text-muted-foreground mb-1">
//                 <CheckCircle className="h-3 w-3 mr-1 text-green-500" />
//                 <span>Done</span>
//               </div>
//               <span className="font-semibold">{props.details?.done || 0}</span>
//             </div>
            
//             <div className="flex flex-col items-center">
//               <div className="flex items-center text-xs text-muted-foreground mb-1">
//                 <XCircle className="h-3 w-3 mr-1 text-red-500" />
//                 <span>Failed</span>
//               </div>
//               <span className="font-semibold">{props.details?.failed || 0}</span>
//             </div>
            
//             <div className="flex flex-col items-center">
//               <div className="flex items-center text-xs text-muted-foreground mb-1">
//                 <Clock className="h-3 w-3 mr-1 text-amber-500" />
//                 <span>Pending</span>
//               </div>
//               <span className="font-semibold">{props.details?.pending || 0}</span>
//             </div>
//           </div>
          
//           {/* Total tasks section */}
//           <div className="flex justify-between text-sm px-1">
//             <span className="font-medium">Total Tasks:</span>
//             <span className="font-semibold">{props.details?.total || 0}</span>
//           </div>
          
//           {/* Task results section - only show if there are completed tasks */}
//           {props.completedLinks && props.completedLinks.length > 0 && (
//             <div className="mt-4">
//               <h4 className="text-sm font-semibold mb-2">Completed Task Results:</h4>
//               <div className="max-h-48 overflow-y-auto bg-muted/30 rounded-md p-2">
//                 <ul className="space-y-2">
//                   {props.completedLinks.map((link, index) => (
//                     <li key={index} className="text-xs flex items-start">
//                       <a href={link} target="_blank" rel="noopener noreferrer" className="flex items-center">
//                         <ExternalLink className="h-3 w-3 mr-1 flex-shrink-0 mt-0.5 text-blue-500" />
//                         <span className="break-all">{link}</span>
//                       </a>
//                     </li>
//                   ))}
//                 </ul>
//               </div>
//             </div>
//           )}
          
//           {/* Failed tasks section - only show if there are failed tasks */}
//           {props.list_failed && props.list_failed.length > 0 && (
//             <div className="mt-4">
//               <h4 className="text-sm font-semibold mb-2 text-red-500 flex items-center">
//                 <AlertCircle className="h-3 w-3 mr-1" />
//                 Failed Tasks:
//               </h4>
//               <div className="max-h-48 overflow-y-auto bg-red-50 rounded-md p-2 border border-red-200">
//                 <ul className="space-y-2">
//                   {props.list_failed.map((item, index) => (
//                     <li key={index} className="text-xs bg-white p-2 rounded shadow-sm border border-red-100">
//                       <div className="flex flex-col">
//                         <span className="font-semibold text-red-600 mb-1">{item.error}</span>
//                         <div className="flex justify-between text-gray-500">
//                           <span>Task ID: {item.task_id}</span>
//                           <span>X ID: {item.x_id}</span>
//                         </div>
//                       </div>
//                     </li>
//                   ))}
//                 </ul>
//               </div>
//             </div>
//           )}
//         </div>
//       </CardContent>
//     </Card>
//   );
// }
