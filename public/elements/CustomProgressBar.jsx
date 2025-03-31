import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { CheckCircle, XCircle, Clock, ExternalLink, AlertCircle } from "lucide-react"

export default function CustomProgressBar() {
  return (
    <Card className="w-full max-w-md">
      <CardHeader className="pb-2">
        <div className="flex justify-between items-center">
          <CardTitle className="text-lg font-medium">
            {props.title || "Jobs to do"}
          </CardTitle>
          {props.value > 0 && (
            <Badge variant={props.value >= 100 ? "success" : "default"} className="ml-2">
              {props.value}%
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
                {props.progressName}
              </span>
            </div>
            <Progress value={props.value || 0} className="h-2" />
          </div>
          
          {/* Task statistics section */}
          <div className="grid grid-cols-3 gap-2 bg-muted/50 p-2 rounded-md">
            <div className="flex flex-col items-center">
              <div className="flex items-center text-xs text-muted-foreground mb-1">
                <CheckCircle className="h-3 w-3 mr-1 text-green-500" />
                <span>Done</span>
              </div>
              <span className="font-semibold">{props.details?.done || 0}</span>
            </div>
            
            <div className="flex flex-col items-center">
              <div className="flex items-center text-xs text-muted-foreground mb-1">
                <XCircle className="h-3 w-3 mr-1 text-red-500" />
                <span>Failed</span>
              </div>
              <span className="font-semibold">{props.details?.failed || 0}</span>
            </div>
            
            <div className="flex flex-col items-center">
              <div className="flex items-center text-xs text-muted-foreground mb-1">
                <Clock className="h-3 w-3 mr-1 text-amber-500" />
                <span>Pending</span>
              </div>
              <span className="font-semibold">{props.details?.pending || 0}</span>
            </div>
          </div>
          
          {/* Total tasks section */}
          <div className="flex justify-between text-sm px-1">
            <span className="font-medium">Total Tasks:</span>
            <span className="font-semibold">{props.details?.total || 0}</span>
          </div>
          
          {/* Task results section - only show if there are completed tasks */}
          {props.completedLinks && props.completedLinks.length > 0 && (
            <div className="mt-4">
              <h4 className="text-sm font-semibold mb-2">Completed Task Results:</h4>
              <div className="max-h-48 overflow-y-auto bg-muted/30 rounded-md p-2">
                <ul className="space-y-2">
                  {props.completedLinks.map((link, index) => (
                    <li key={index} className="text-xs flex items-start">
                      <a href={link} target="_blank" rel="noopener noreferrer" className="flex items-center">
                        <ExternalLink className="h-3 w-3 mr-1 flex-shrink-0 mt-0.5 text-blue-500" />
                        <span className="break-all">{link}</span>
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
          
          {/* Failed tasks section - only show if there are failed tasks */}
          {props.list_failed && props.list_failed.length > 0 && (
            <div className="mt-4">
              <h4 className="text-sm font-semibold mb-2 text-red-500 flex items-center">
                <AlertCircle className="h-3 w-3 mr-1" />
                Failed Tasks:
              </h4>
              <div className="max-h-48 overflow-y-auto bg-red-50 rounded-md p-2 border border-red-200">
                <ul className="space-y-2">
                  {props.list_failed.map((item, index) => (
                    <li key={index} className="text-xs bg-white p-2 rounded shadow-sm border border-red-100">
                      <div className="flex flex-col">
                        <span className="font-semibold text-red-600 mb-1">{item.error}</span>
                        <div className="flex justify-between text-gray-500">
                          <span>Task ID: {item.task_id}</span>
                          <span>X ID: {item.x_id}</span>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
// import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
// import { Badge } from "@/components/ui/badge"
// import { Progress } from "@/components/ui/progress"
// import { CheckCircle, XCircle, Clock, ExternalLink, AlertCircle, Hash } from "lucide-react"

// export default function CustomProgressBar() {
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
//               <h4 className="text-sm font-semibold mb-2 flex items-center">
//                 <CheckCircle className="h-3 w-3 mr-1 text-green-500" />
//                 Completed Task Results:
//               </h4>
//               <div className="max-h-48 overflow-y-auto bg-muted/30 rounded-md p-2">
//                 <ul className="space-y-2">
//                   {props.completedLinks.map((item, index) => (
//                     <li key={index} className="text-xs bg-white p-2 rounded shadow-sm border border-green-100">
//                       <div className="flex flex-col">
//                         <div className="flex items-center mb-1">
//                           <a 
//                             href={`https://twitter.com/i/web/status/${item.data}`} 
//                             target="_blank" 
//                             rel="noopener noreferrer" 
//                             className="text-blue-600 font-medium flex items-center"
//                           >
//                             <ExternalLink className="h-3 w-3 mr-1 flex-shrink-0" />
//                             https://twitter.com/i/web/status/${item.data}
//                           </a>
//                         </div>
//                         <div className="flex justify-between text-gray-500 text-[10px] mt-1">
//                           <span className="flex items-center">
//                             <Hash className="h-2.5 w-2.5 mr-1" />
//                             Task: {item.task_id?.substring(0, 8) || "N/A"}
//                           </span>
//                           <span>X ID: {item.id}</span>
//                         </div>
//                       </div>
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
//                           <span>Task ID: {item.task_id || "N/A"}</span>
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