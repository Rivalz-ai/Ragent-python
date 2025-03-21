// import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
// import { Badge } from "@/components/ui/badge"
// import { Progress } from "@/components/ui/progress"
// import { Clock, User, Tag } from "lucide-react"

// export default function CustomProgressBar() {
//   return (
//     <Card className="w-full max-w-md">
//       <CardHeader className="pb-2">
//         <div className="flex justify-between items-center">
//           <CardTitle className="text-lg font-medium">
//             {props.title || "Jobs to do"}
//           </CardTitle>
//         </div>
//       </CardHeader>

//       <CardContent>
//         <div className="space-y-4">
//           <span className="text-sm font-semibold">
//             {props.progressName || "RX post"}
//           </span>
//           <Progress value={props.value||10} className="h-2" />
//         </div>
//       </CardContent>
//     </Card>
//   )
// }
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { CheckCircle, XCircle, Clock, ExternalLink } from "lucide-react"

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
                      <ExternalLink className="h-3 w-3 mr-1 flex-shrink-0 mt-0.5 text-blue-500" />
                      <span className="break-all">{link}</span>
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